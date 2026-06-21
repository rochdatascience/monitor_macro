"""
ETL IPCA por RM e Municípios (Tabela 7060 - SIDRA/IBGE)

Extrai o grupo "Alimentação e bebidas" (c315/7169) por Região Metropolitana
e Município, anexa coordenadas geográficas e salva em Parquet (tipos preservados).
"""
import logging
import os
import time
from typing import Dict, Optional

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "periodo_extracao": "last 1",          # ex: "last 1", "last 12", "202001-202612"
    "grupo": "7169",                       # 7169 = Alimentação e bebidas
    "dest_path": "./dados_ipca",
    "output_filename": "ipca_7060_rm_municipios.parquet",
    "tentativas": 3,
    "espera_seg": 10,
}

NIVEIS = {
    "7": "Região Metropolitana",
    "6": "Município",
}

COL_MES_COD  = "Mês (Código)"
COL_NT_COD   = "Nível Territorial (Código)"
COL_ITEM_COD = "Geral, grupo, subgrupo, item e subitem (Código)"
COL_VARIAVEL = "Variável"
COL_VALOR    = "Valor"
CHAVE_GEO_NOME = "D1N"
CHAVE_GEO_COD  = "D1C"

# Centróides das áreas mapeadas
COORDENADAS = {
    "Belém - PA":          (-1.4558,  -48.5044),
    "Fortaleza - CE":      (-3.7172,  -38.5433),
    "Recife - PE":         (-8.0476,  -34.8770),
    "Salvador - BA":       (-12.9714, -38.5014),
    "Belo Horizonte - MG": (-19.9167, -43.9345),
    "Grande Vitória - ES": (-20.3155, -40.3128),
    "Rio de Janeiro - RJ": (-22.9068, -43.1729),
    "São Paulo - SP":      (-23.5505, -46.6333),
    "Curitiba - PR":       (-25.4284, -49.2733),
    "Porto Alegre - RS":   (-30.0346, -51.2177),
    "Goiânia - GO":        (-16.6869, -49.2648),
    "Brasília - DF":       (-15.7942, -47.8825),
    "Campo Grande - MS":   (-20.4697, -54.6201),
    "Rio Branco - AC":     (-9.9754,  -67.8249),
    "São Luís - MA":       (-2.5297,  -44.3028),
    "Aracaju - SE":        (-10.9472, -37.0731),
}


def _montar_url(nivel: str, periodo: str, grupo: str) -> str:
    base = "https://apisidra.ibge.gov.br/values"
    return (
        f"{base}/t/7060/n{nivel}/all/v/63,66,69,2265"
        f"/p/{periodo}/c315/{grupo}"
        f"/d/v63%202,v66%204,v69%202,v2265%202"
    )


def _baixar_nivel(nivel: str, nome_nivel: str, cfg: dict) -> pd.DataFrame:
    url = _montar_url(nivel, cfg["periodo_extracao"], cfg["grupo"])
    logger.info("Buscando nível %s: %s", nome_nivel, url)

    for tentativa in range(1, cfg["tentativas"] + 1):
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            dados = resp.json()
            
            cabecalho, registros = dados[0], dados[1:]
            nome_geo_cod  = cabecalho.get(CHAVE_GEO_COD,  CHAVE_GEO_COD)
            nome_geo_nome = cabecalho.get(CHAVE_GEO_NOME, CHAVE_GEO_NOME)

            df = pd.DataFrame(registros).rename(columns=cabecalho)
            df["Nivel_Territorial"] = nome_nivel
            df = df.rename(columns={nome_geo_cod: "Geo_Codigo", nome_geo_nome: "Geo_Nome"})
            
            logger.info("%s: %d registros coletados.", nome_nivel, len(df))
            return df
            
        except requests.exceptions.Timeout:
            logger.warning("Timeout (tentativa %d/%d) no nível %s", tentativa, cfg["tentativas"], nivel)
            if tentativa < cfg["tentativas"]:
                time.sleep(cfg["espera_seg"])
            else:
                raise
        except Exception as e:
            logger.error("Erro ao baixar nível %s: %s", nivel, e)
            raise


def _adicionar_coordenadas(df: pd.DataFrame) -> pd.DataFrame:
    coords_df = (
        pd.DataFrame.from_dict(COORDENADAS, orient="index",
                               columns=["Latitude", "Longitude"])
        .reset_index().rename(columns={"index": "Geo_Nome"})
    )
    df_out = df.merge(coords_df, on="Geo_Nome", how="left")
    
    sem_coord = df_out[df_out["Latitude"].isna()]["Geo_Nome"].unique()
    if len(sem_coord):
        logger.warning("Áreas sem coordenadas mapeadas: %s", list(sem_coord))
        
    return df_out


def executar(params: Optional[Dict] = None) -> str:
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    logger.info("=== Iniciando ETL: IPCA 7060 RM/Municípios ===")
    logger.info("Período extração: %s", cfg["periodo_extracao"])

    dfs = []
    for nivel, nome_nivel in NIVEIS.items():
        try:
            dfs.append(_baixar_nivel(nivel, nome_nivel, cfg))
        except Exception as e:
            logger.error("Ignorando nível %s devido a erro crítico: %s", nivel, e)

    if not dfs:
        raise RuntimeError("Nenhum dado coletado.")

    df_all = pd.concat(dfs, ignore_index=True)

    # Limpeza do campo valor
    df_all[COL_VALOR] = pd.to_numeric(
        df_all[COL_VALOR].astype(str).str.replace(",", "."), errors="coerce"
    )

    # Pivotagem
    idx_cols = [c for c in [
        COL_MES_COD, "Mês", "Nivel_Territorial", COL_NT_COD,
        "Geo_Codigo", "Geo_Nome", COL_ITEM_COD, "Geral, grupo, subgrupo, item e subitem"
    ] if c in df_all.columns]
    
    df_pivot = (
        df_all.pivot_table(index=idx_cols, columns=COL_VARIAVEL,
                           values=COL_VALOR, aggfunc="first")
        .reset_index()
    )
    df_pivot.columns.name = None

    # Tipagem rigorosa
    df_pivot = _adicionar_coordenadas(df_pivot)
    for col in [COL_MES_COD, COL_NT_COD, COL_ITEM_COD, "Geo_Codigo"]:
        if col in df_pivot.columns:
            df_pivot[col] = pd.to_numeric(df_pivot[col], errors="coerce").astype("Int64")

    # Salvamento
    os.makedirs(cfg["dest_path"], exist_ok=True)
    arquivo = os.path.join(cfg["dest_path"], cfg["output_filename"])
    df_pivot.to_parquet(arquivo, index=False, engine="pyarrow")

    mes_ref = df_pivot[COL_MES_COD].iloc[0] if len(df_pivot) else "?"
    logger.info("=== ETL Finalizado ===")
    logger.info("Arquivo Parquet salvo: %s | ref %s | %d regs", arquivo, mes_ref, len(df_pivot))
    
    return arquivo

if __name__ == "__main__":
    executar()
