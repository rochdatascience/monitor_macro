"""
Metas de Inflação (SGS/BCB - série 13521)

Busca a meta de inflação na API pública do Banco Central, expande para
formato mensal com bandas de tolerância superior/inferior.
"""
import logging
import os
import time
from typing import Dict, Optional

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

COL_META = "13521 - Meta para a inflação - %"
COL_SUP = "Limite Superior"
COL_INF = "Limite Inferior"

DEFAULT_CONFIG = {
    "serie_sgs": "13521",
    "dest_path": "./dados_ipca",
    "output_filename": "meta_inflacao.parquet",
    "tentativas": 3,
    "espera_seg": 10,
}


def _margem_banda(ano: int) -> float:
    """Banda de tolerância: 2.0 até 2005 e 2017-2018; 1.5 no resto."""
    if ano <= 2005 or (2017 <= ano <= 2018):
        return 2.0
    return 1.5


def _extrair(cfg: dict) -> pd.DataFrame:
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cfg['serie_sgs']}/dados?formato=json"
    logger.info("Buscando meta BCB: %s", url)

    for tentativa in range(1, cfg["tentativas"] + 1):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            dados = resp.json()

            if not dados:
                raise ValueError("API retornou resposta vazia.")

            df = pd.DataFrame(dados)
            df["ano"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.year
            df["meta"] = pd.to_numeric(df["valor"], errors="coerce")
            return df[["ano", "meta"]]

        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning("Falha (tentativa %d/%d): %s", tentativa, cfg["tentativas"], e)
            if tentativa < cfg["tentativas"]:
                time.sleep(cfg["espera_seg"])
            else:
                raise

    # Salvaguarda: o loop sempre retorna ou levanta exceção acima,
    # mas garantimos que a função nunca devolva None silenciosamente.
    raise RuntimeError("Extração da meta de inflação falhou sem exceção explícita.")


def _transformar(df: pd.DataFrame) -> pd.DataFrame:
    # Expande o ano em 12 meses
    df = df.assign(mes=[list(range(1, 13))] * len(df)).explode("mes")
    df["mes"] = df["mes"].astype(int)

    # Calculo das bandas
    margem = df["ano"].apply(_margem_banda)
    df[COL_META] = df["meta"]
    df[COL_SUP] = df["meta"] + margem
    df[COL_INF] = df["meta"] - margem

    df["Mês (Código)"] = (df["ano"] * 100 + df["mes"]).astype("Int64")
    df["Data"] = df["ano"].astype("Int64")

    # Ordenação e filtros finais
    df = df[["Data", COL_META, "Mês (Código)", COL_SUP, COL_INF]]
    df = df.sort_values("Mês (Código)").reset_index(drop=True)
    return df


def executar(params: Optional[Dict] = None) -> str:
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    logger.info("=== Iniciando ETL: Meta de Inflação (BCB) ===")
    
    df_bruto = _extrair(cfg)
    df_limpo = _transformar(df_bruto)
    
    os.makedirs(cfg["dest_path"], exist_ok=True)
    arquivo = os.path.join(cfg["dest_path"], cfg["output_filename"])
    df_limpo.to_parquet(arquivo, index=False, engine="pyarrow")
    
    logger.info("=== ETL finalizado ===")
    logger.info("Arquivo Parquet salvo: %s (%d registros)", arquivo, len(df_limpo))
    return arquivo

if __name__ == "__main__":
    executar()
