"""
Carga das tabelas processadas no PostgreSQL.

Lê os arquivos .parquet gerados pelo orquestrador e escreve cada um em uma
tabela do PostgreSQL (full refresh por padrão). Mantém a arquitetura
desacoplada: o processamento já foi feito e salvo localmente; aqui apenas
carregamos para o banco. Pode ser re-executado isoladamente em caso de falha.
"""
import logging
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()

# Configurações do PostgreSQL
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_SCHEMA = os.getenv("PG_SCHEMA", "public")

DIRETORIO_DADOS = "./dados_ipca"

# Estratégia de escrita: "replace" recria a tabela a cada execução (full refresh),
# coerente com os nomes de arquivo estáveis e extrações completas do pipeline.
IF_EXISTS = "replace"


def get_engine():
    faltando = [k for k, v in {
        "PG_HOST": PG_HOST, "PG_DATABASE": PG_DATABASE,
        "PG_USER": PG_USER, "PG_PASSWORD": PG_PASSWORD,
    }.items() if not v]
    if faltando:
        raise RuntimeError(f"Variáveis de ambiente do PostgreSQL ausentes: {faltando}")

    # URL.create faz o escape correto de caracteres especiais na senha (@, !, etc.).
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=int(PG_PORT),
        database=PG_DATABASE,
    )
    return create_engine(url)


def _nome_tabela(arquivo: str) -> str:
    """Deriva o nome da tabela a partir do nome do arquivo (.parquet -> tabela)."""
    return os.path.splitext(arquivo)[0].lower()


def carregar_arquivos(engine, diretorio: str) -> int:
    """Escreve cada .parquet em uma tabela e retorna o número de falhas."""
    if not os.path.exists(diretorio):
        logging.error(f"O diretório {diretorio} não existe.")
        return 1

    arquivos = [f for f in os.listdir(diretorio) if f.endswith(".parquet")]

    if not arquivos:
        logging.warning("Nenhum arquivo .parquet encontrado para carga.")
        return 0

    falhas = 0
    for arquivo in arquivos:
        caminho_local = os.path.join(diretorio, arquivo)
        tabela = _nome_tabela(arquivo)

        logging.info(f"Carregando '{arquivo}' -> {PG_SCHEMA}.{tabela} ...")
        try:
            df = pd.read_parquet(caminho_local, engine="pyarrow")
            df.to_sql(
                name=tabela,
                con=engine,
                schema=PG_SCHEMA,
                if_exists=IF_EXISTS,
                index=False,
            )
            logging.info(
                f"Tabela '{PG_SCHEMA}.{tabela}' carregada com sucesso "
                f"({len(df)} linhas x {df.shape[1]} colunas)."
            )
        except Exception as e:
            logging.error(f"Erro ao carregar '{arquivo}': {e}")
            falhas += 1

    return falhas


def main():
    logging.info("Iniciando carga das tabelas no PostgreSQL...")
    engine = get_engine()

    try:
        falhas = carregar_arquivos(engine, DIRETORIO_DADOS)
    finally:
        engine.dispose()

    if falhas:
        logging.error("Processo finalizado com %d falha(s) de carga.", falhas)
        sys.exit(1)

    logging.info("Processo finalizado!")


if __name__ == "__main__":
    main()
