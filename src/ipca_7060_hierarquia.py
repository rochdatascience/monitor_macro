"""
ETL IPCA Hierárquico (Tabela 7060 c315/all - SIDRA/IBGE)

Extrai TODOS os níveis da classificação 315 (geral, grupo, subgrupo, item, subitem),
identifica o nível e a hierarquia EM PYTHON e salva em Parquet servido pelo Apache.

A API do SIDRA limita 50.000 valores por requisição -> a extração é FATIADA em
blocos de período (padrão: 12 meses) e os blocos são concatenados.
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
    "start_period": "202001",
    "dest_path": "./dados_ipca",
    "output_filename": "ipca_7060_hierarquia.parquet",
    "meses_por_bloco": 12,   # 12 meses ~ 22 mil valores (< limite de 50 mil)
}

COL_DESC = "Geral, grupo, subgrupo, item e subitem"
RENOMEAR = {
    "IPCA - Peso mensal": "Peso",
    "IPCA - Variação acumulada em 12 meses": "Var_12m",
    "IPCA - Variação acumulada no ano": "Var_Ano",
    "IPCA - Variação mensal": "Var_Mensal",
}
NIVEL_POR_TAMANHO = {1: "Grupo", 2: "Subgrupo", 4: "Item", 7: "Subitem"}


def _blocos_periodo(inicio: str, fim: str, meses: int) -> list:
    """Gera blocos de períodos para contornar limites da API."""
    dt_ini = pd.to_datetime(inicio, format="%Y%m")
    dt_fim = pd.to_datetime(fim, format="%Y%m")
    datas = pd.period_range(start=dt_ini, end=dt_fim, freq="M")
    blocos = []
    for i in range(0, len(datas), meses):
        janela = datas[i:i + meses]
        blocos.append(f"{janela[0].strftime('%Y%m')}-{janela[-1].strftime('%Y%m')}")
    return blocos


def _extrair(cfg: dict, periodo_final: str) -> pd.DataFrame:
    blocos = _blocos_periodo(cfg["start_period"], periodo_final, cfg["meses_por_bloco"])
    logger.info("Extração fatiada em %d bloco(s): %s", len(blocos), blocos)

    partes = []
    for bloco in blocos:
        logger.info("Extraindo bloco %s ...", bloco)
        df = sidrapy.get_table(
            table_code="7060",
            territorial_level="1",
            ibge_territorial_code="all",
            variable="63,66,69,2265",
            period=bloco,
            classification="315/all",
        )
        if df is None or df.empty:
            logger.warning("Bloco %s veio vazio.", bloco)
            continue
        
        # O cabeçalho vem na linha 0 em cada bloco
        df.columns = df.iloc[0]
        df = df.iloc[1:].copy()
        partes.append(df)
        logger.info("Bloco %s finalizado: %d linhas.", bloco, len(df))

    if not partes:
        raise ValueError("Nenhum dado retornado em nenhum bloco.")

    df_all = pd.concat(partes, ignore_index=True)
    logger.info("Extração total: %d linhas brutas coletadas.", len(df_all))
    return df_all


def _classificar_nivel(codigo) -> str:
    if pd.isna(codigo) or codigo == "":
        return "Geral"
    return NIVEL_POR_TAMANHO.get(len(str(codigo)), "Outro")


def _transformar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Valor"] = pd.to_numeric(df["Valor"].str.replace(",", "."), errors="coerce")

    # Pivotagem
    df_pivot = df.pivot_table(
        index=["Mês (Código)", "Mês", COL_DESC],
        columns="Variável", values="Valor", aggfunc="first",
    ).reset_index()
    
    df_pivot.columns.name = None
    df_pivot = df_pivot.rename(columns=RENOMEAR)
    df_pivot = df_pivot.rename(columns={COL_DESC: "DescricaoCompleta"})

    # Separação de código e descrição (ex: "11.Cereais" -> "11", "Cereais")
    partes = df_pivot["DescricaoCompleta"].astype(str).str.split(".", n=1, expand=True)
    tem_ponto = partes[1].notna()
    
    df_pivot["codigo"] = partes[0].where(tem_ponto, other=pd.NA).str.strip()
    df_pivot["descricao"] = partes[1].where(tem_ponto, other=partes[0]).str.strip()

    # Aplicação de hierarquia
    df_pivot["nivel"] = df_pivot["codigo"].apply(_classificar_nivel)

    def _pref(c, n):
        return str(c)[:n] if (pd.notna(c) and len(str(c)) >= n) else pd.NA
        
    df_pivot["grupo"]    = df_pivot["codigo"].apply(lambda c: _pref(c, 1))
    df_pivot["subgrupo"] = df_pivot["codigo"].apply(lambda c: _pref(c, 2))
    df_pivot["item"]     = df_pivot["codigo"].apply(lambda c: _pref(c, 4))

    # Tipagem de datas
    df_pivot["Data"] = pd.to_datetime(df_pivot["Mês (Código)"], format="%Y%m")
    df_pivot["Mês (Código)"] = pd.to_numeric(df_pivot["Mês (Código)"], errors="coerce").astype("Int64")

    logger.info("Distribuição de níveis: %s", df_pivot["nivel"].value_counts().to_dict())
    logger.info("Transformação concluída: %d linhas x %d colunas.", *df_pivot.shape)
    return df_pivot


def _carregar(df_pivot: pd.DataFrame, cfg: dict) -> str:
    os.makedirs(cfg["dest_path"], exist_ok=True)
    arquivo = os.path.join(cfg["dest_path"], cfg["output_filename"])
    df_pivot.to_parquet(arquivo, index=False, engine="pyarrow")
    logger.info("Arquivo Parquet salvo com sucesso: %s (%d registros)", arquivo, len(df_pivot))
    return arquivo


def executar(params: Optional[Dict] = None) -> str:
    """Função principal que orquestra o ETL."""
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    
    periodo_final = pendulum.now(TIMEZONE).strftime("%Y%m")
    logger.info("=== Iniciando ETL: IPCA 7060 Hierarquia ===")
    logger.info("Período final (mês atual): %s", periodo_final)
    
    df_bruto = _extrair(cfg, periodo_final)
    df_limpo = _transformar(df_bruto)
    caminho_arquivo = _carregar(df_limpo, cfg)
    
    logger.info("=== ETL finalizado com sucesso ===")
    return caminho_arquivo

if __name__ == "__main__":
    executar()
