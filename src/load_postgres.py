"""
Camada de carga — lê os parquets da pasta local e carrega no PostgreSQL
(schema macroeconomia), construindo o modelo estrela.

Por que separar da extração?
Se a rede/o banco cair, a extração (parquet local) já está salva; basta rodar
este script novamente mais tarde. A carga é idempotente (UPSERT por chave).
"""
import logging
from pathlib import Path

import pandas as pd

from config_indicadores import INDICADORES
from utils import get_engine, output_dir, schema

logger = logging.getLogger("load_postgres")

DDL_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema_macroeconomia.sql"

MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _criar_schema(engine):
    """Executa o DDL idempotente que cria schema, dimensões e fato."""
    ddl = DDL_PATH.read_text(encoding="utf-8")
    # Script inteiro numa única chamada: o psycopg2 aceita múltiplos statements
    # e isso não quebra se o DDL ganhar functions/triggers com ';' interno.
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)
    logger.info("Schema/tabelas garantidos (%s).", schema())


def _ler_fatos() -> pd.DataFrame:
    """Concatena todos os parquets 'fato_*.parquet' da pasta local."""
    arquivos = sorted(output_dir().glob("fato_*.parquet"))
    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum parquet 'fato_*' em {output_dir()}. Rode o orquestrador antes."
        )
    df = pd.concat([pd.read_parquet(a) for a in arquivos], ignore_index=True)
    df["data"] = pd.to_datetime(df["data"])
    df = df.drop_duplicates(subset=["data", "indicador_id"], keep="last")
    logger.info("%d fatos lidos de %d arquivos.", len(df), len(arquivos))
    return df


def _upsert(engine, sch, tabela, df, colunas, chave):
    """
    UPSERT em lote via psycopg2.execute_values: uma única ida ao banco para
    milhares de linhas (essencial em conexões remotas de alta latência).
    """
    if df.empty:
        return
    from psycopg2.extras import execute_values

    cols = ", ".join(colunas)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in colunas if c not in chave)
    sql = (
        f"INSERT INTO {sch}.{tabela} ({cols}) VALUES %s "
        f"ON CONFLICT ({', '.join(chave)}) DO UPDATE SET {updates}"
    )
    registros = list(df[colunas].itertuples(index=False, name=None))
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            execute_values(cur, sql, registros, page_size=1000)
        raw.commit()
    finally:
        raw.close()
    logger.info("UPSERT %-18s -> %d linhas.", tabela, len(registros))


def _carregar_dim_indicador(engine, sch):
    df = pd.DataFrame(INDICADORES)[
        ["id", "nome", "categoria", "unidade", "fonte", "codigo"]
    ].rename(columns={"id": "indicador_id"})
    _upsert(engine, sch, "dim_indicador", df,
            ["indicador_id", "nome", "categoria", "unidade", "fonte", "codigo"],
            ["indicador_id"])


def _carregar_dim_data(engine, sch, fatos):
    datas = pd.DataFrame({"data": pd.to_datetime(fatos["data"].unique())})
    datas["data_id"] = datas["data"].dt.strftime("%Y%m%d").astype(int)
    datas["ano"] = datas["data"].dt.year
    datas["mes"] = datas["data"].dt.month
    datas["dia"] = datas["data"].dt.day
    datas["trimestre"] = datas["data"].dt.quarter
    datas["nome_mes"] = datas["mes"].map(lambda m: MESES_PT[m - 1])
    datas["dia_semana"] = datas["data"].dt.weekday
    datas["data"] = datas["data"].dt.date
    _upsert(engine, sch, "dim_data", datas,
            ["data_id", "data", "ano", "mes", "dia", "trimestre", "nome_mes", "dia_semana"],
            ["data_id"])


def _carregar_fato(engine, sch, fatos):
    f = fatos.copy()
    f["data_id"] = pd.to_datetime(f["data"]).dt.strftime("%Y%m%d").astype(int)
    f["valor"] = pd.to_numeric(f["valor"], errors="coerce")
    f = f.dropna(subset=["valor"])
    _upsert(engine, sch, "fat_macroeconomia", f,
            ["data_id", "indicador_id", "valor"],
            ["data_id", "indicador_id"])


def executar():
    engine = get_engine()
    sch = schema()
    logger.info("Iniciando carga no PostgreSQL (schema=%s)...", sch)
    _criar_schema(engine)
    fatos = _ler_fatos()
    _carregar_dim_indicador(engine, sch)
    _carregar_dim_data(engine, sch, fatos)
    _carregar_fato(engine, sch, fatos)
    logger.info("Carga concluída com sucesso.")


if __name__ == "__main__":
    from utils import configurar_logging

    configurar_logging()
    executar()
