"""
Utilitários compartilhados: configuração de logging, leitura de .env,
salvamento de parquet e criação da engine PostgreSQL.

Mantém os pipelines DRY sem acoplá-los entre si.
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Carrega o .env a partir da raiz do projeto (um nível acima de src/)
_RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(_RAIZ / ".env")


def configurar_logging():
    """Configura o logging padrão do projeto (idempotente)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )


def output_dir() -> Path:
    """Pasta temporária onde os parquets são gravados na camada local."""
    caminho = Path(os.getenv("ETL_OUTPUT_DIR", "./dados_processados"))
    if not caminho.is_absolute():
        caminho = _RAIZ / caminho
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def dias_historico() -> int:
    return int(os.getenv("ETL_DIAS_HISTORICO", "400"))


def janela_datas():
    """Retorna (data_inicial, data_final) como objetos date para a extração."""
    fim = datetime.now().date()
    inicio = fim - timedelta(days=dias_historico())
    return inicio, fim


def salvar_parquet(df: pd.DataFrame, nome: str) -> Path:
    """Salva o DataFrame em ./dados_processados/<nome>.parquet."""
    destino = output_dir() / f"{nome}.parquet"
    df.to_parquet(destino, index=False)
    logging.getLogger(nome).info("Parquet salvo: %s (%d linhas)", destino, len(df))
    return destino


def padronizar_fato(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante o contrato de saída de todo pipeline:
    colunas [data (date), indicador_id (int), valor (float)], sem nulos/duplicatas.
    """
    df = df[["data", "indicador_id", "valor"]].copy()
    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["indicador_id"] = df["indicador_id"].astype("int64")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["valor"])
    df = df.drop_duplicates(subset=["data", "indicador_id"], keep="last")
    return df.reset_index(drop=True)


def get_engine():
    """Cria uma SQLAlchemy Engine para o PostgreSQL a partir do .env."""
    from sqlalchemy import create_engine
    from urllib.parse import quote_plus

    user = os.environ["PG_USER"]
    pwd = quote_plus(os.environ["PG_PASSWORD"])
    host = os.environ["PG_HOST"]
    port = os.getenv("PG_PORT", "5432")
    db = os.environ["PG_DATABASE"]
    url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True)


def schema() -> str:
    return os.getenv("PG_SCHEMA", "macroeconomia")
