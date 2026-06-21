"""
ETL da Série Histórica do IPCA (Tabela 1737 - SIDRA/IBGE)

Processa dados históricos e consolida em arquivos para o Power BI.
"""
import logging
import os
from typing import Dict, Optional

import pandas as pd
import pendulum
import sidrapy

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TIMEZONE = "America/Sao_Paulo"

DEFAULT_CONFIG = {
    "table_code": "1737",
    "territorial_level": "1",
    "ibge_territorial_code": "all",
    "variables": "2266,63,69,2265",
    "start_period": "199312",          # base do Plano Real
    "dest_path": "./dados_ipca",
    "output_filename": "ipca_1737_master",
    "output_format": "parquet",        # "parquet" ou "csv"
}


def _extrair(cfg: dict, periodo_final: str) -> pd.DataFrame:
    logger.info("Extraindo tabela %s | período %s-%s", 
                cfg["table_code"], cfg["start_period"], periodo_final)
    
    df = sidrapy.get_table(
        table_code=cfg["table_code"],
        territorial_level=cfg["territorial_level"],
        ibge_territorial_code=cfg["ibge_territorial_code"],
        variable=cfg["variables"],
        period=f"{cfg['start_period']}-{periodo_final}",
    )
    if df is None or df.empty:
        raise ValueError("A API do SIDRA retornou um conjunto de dados vazio.")
        
    logger.info("Extração concluída: %d linhas brutas recebidas.", len(df))
    return df


def _transformar(df: pd.DataFrame) -> pd.DataFrame:
    # Cabeçalho na linha 1
    df.columns = df.iloc[0]
    df = df.iloc[1:].copy()

    # Tipagem
    df["Valor"] = pd.to_numeric(df["Valor"].str.replace(",", "."), errors="coerce")

    # Pivotagem
    df_pivot = df.pivot_table(
        index=["Mês (Código)", "Mês"],
        columns="Variável",
        values="Valor",
    ).reset_index()
    
    logger.info("Transformação concluída: %d linhas x %d colunas.", *df_pivot.shape)
    return df_pivot


def executar(params: Optional[Dict] = None) -> str:
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    periodo_final = pendulum.now(TIMEZONE).strftime("%Y%m")
    
    logger.info("=== Iniciando ETL: IPCA Série Histórica ===")
    
    df_bruto = _extrair(cfg, periodo_final)
    df_final = _transformar(df_bruto)
    
    os.makedirs(cfg["dest_path"], exist_ok=True)
    fmt = cfg["output_format"].lower()

    if fmt == "parquet":
        arquivo = os.path.join(cfg["dest_path"], f"{cfg['output_filename']}.parquet")
        df_final.to_parquet(arquivo, index=False, engine="pyarrow")
    else:
        arquivo = os.path.join(cfg["dest_path"], f"{cfg['output_filename']}.csv")
        df_csv = df_final.copy()
        for col in df_csv.columns.drop(["Mês (Código)", "Mês"]):
            df_csv[col] = df_csv[col].apply(lambda x: str(x).replace(".", ",") if pd.notnull(x) else "")
        df_csv.to_csv(arquivo, index=False, sep=";", encoding="utf-8-sig")

    logger.info("=== ETL finalizado ===")
    logger.info("Arquivo salvo (%s): %s", fmt, arquivo)
    return arquivo

if __name__ == "__main__":
    executar()
