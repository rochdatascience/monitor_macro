"""
ETL IPCA por Grupos (Tabela 7060 - SIDRA/IBGE)

Extrai os 9 grupos do IPCA a nível nacional (classif. 315), calcula o impacto
aproximado de cada grupo e salva em Parquet (tipos preservados) na pasta
destinada, para consumo no Power BI. Nome de arquivo ESTÁVEL.
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
    # 9 grupos (sem subitens/subgrupos/itens):
    "grupos": "7169,7170,7445,7486,7558,7625,7660,7712,7766",
    "dest_path": "./dados_ipca", # Alterado para pasta local por padrão
    "output_filename": "ipca_7060_grupos.parquet",
}

RENOMEAR_VARIAVEIS = {
    "IPCA - Variação mensal": "Var_Mensal",
    "IPCA - Variação acumulada no ano": "Var_Acum_Ano",
    "IPCA - Variação acumulada em 12 meses": "Var_Acum_12M",
    "IPCA - Peso mensal": "Peso_Mensal",
}


def _extrair(cfg: dict, periodo_final: str) -> pd.DataFrame:
    """Busca dados brutos da API do SIDRA."""
    logger.info("Extraindo 7060 grupos | período %s-%s", cfg["start_period"], periodo_final)
    df = sidrapy.get_table(
        table_code="7060",
        territorial_level="1",
        ibge_territorial_code="all",
        variable="63,66,69,2265",
        period=f"{cfg['start_period']}-{periodo_final}",
        classification=f"315/{cfg['grupos']}",
    )
    if df is None or df.empty:
        raise ValueError("A API do SIDRA retornou vazio.")
    logger.info("Extração concluída: %d linhas brutas.", len(df))
    return df


def _transformar(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa e formata os dados para análise."""
    # Cabeçalho real está na primeira linha
    df.columns = df.iloc[0]
    df = df.iloc[1:].copy()

    # Conversão de valores numéricos
    df["Valor"] = pd.to_numeric(df["Valor"].str.replace(",", "."), errors="coerce")

    # Renomeia e limpa o nome do grupo (remove prefixos como "1." "2." etc.)
    df = df.rename(columns={"Geral, grupo, subgrupo, item e subitem": "Grupo"})
    df["Grupo"] = df["Grupo"].str.replace(r"^\d+\.", "", regex=True).str.strip()

    # Pivot: Transforma variáveis em colunas
    df_pivot = df.pivot_table(
        index=["Mês (Código)", "Mês", "Grupo"],
        columns="Variável", values="Valor",
    ).reset_index()
    df_pivot.columns.name = None

    # Aplica nomes curtos e padronizados
    df_pivot = df_pivot.rename(columns=RENOMEAR_VARIAVEIS)

    # Verifica se as colunas necessárias para cálculo de impacto existem
    faltando = [c for c in ("Peso_Mensal", "Var_Mensal") if c not in df_pivot.columns]
    if faltando:
        logger.warning("Colunas ausentes após pivot: %s | colunas atuais: %s",
                       faltando, list(df_pivot.columns))

    # Calcula impacto aproximado (Peso x Variação / 100)
    if "Peso_Mensal" in df_pivot.columns and "Var_Mensal" in df_pivot.columns:
        df_pivot["Impacto_PP"] = (df_pivot["Peso_Mensal"] * df_pivot["Var_Mensal"] / 100).round(4)

    # Criação da coluna Data (1º dia do mês) e tipagem do código do mês
    df_pivot["Data"] = pd.to_datetime(df_pivot["Mês (Código)"], format="%Y%m")
    df_pivot["Mês (Código)"] = pd.to_numeric(df_pivot["Mês (Código)"], errors="coerce").astype("Int64")

    # Ordenação lógica
    ordenar_por = ["Data", "Impacto_PP"] if "Impacto_PP" in df_pivot.columns else ["Data"]
    asc = [True, False] if "Impacto_PP" in df_pivot.columns else [True]
    df_pivot = df_pivot.sort_values(ordenar_por, ascending=asc)

    logger.info("Transformação concluída: %d linhas x %d colunas | %d grupos únicos.",
                *df_pivot.shape, df_pivot["Grupo"].nunique())
    return df_pivot


def _carregar(df_pivot: pd.DataFrame, cfg: dict) -> str:
    """Salva os dados no formato Parquet."""
    os.makedirs(cfg["dest_path"], exist_ok=True)
    arquivo = os.path.join(cfg["dest_path"], cfg["output_filename"])
    
    df_pivot.to_parquet(arquivo, index=False, engine="pyarrow")
    logger.info("Arquivo Parquet salvo com sucesso em: %s (%d registros)", arquivo, len(df_pivot))
    return arquivo


def executar(params: Optional[Dict] = None) -> str:
    """Função principal que orquestra o ETL."""
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    
    periodo_final = pendulum.now(TIMEZONE).strftime("%Y%m")
    logger.info("=== Iniciando ETL: IPCA 7060 Grupos ===")
    logger.info("Período final de extração (mês atual): %s", periodo_final)

    df_bruto = _extrair(cfg, periodo_final)
    df_limpo = _transformar(df_bruto)
    caminho_arquivo = _carregar(df_limpo, cfg)
    
    logger.info("=== ETL finalizado com sucesso ===")
    return caminho_arquivo

if __name__ == "__main__":
    executar()
