"""
Pipeline especialista — Banco Central do Brasil (API SGS).

Indicadores: Dólar PTAX, Selic Meta e CDI.
Doc: https://www3.bcb.gov.br/sgspub/  | API: https://api.bcb.gov.br/dados/serie/...
"""
import logging
import time

import pandas as pd
import requests

from config_indicadores import por_fonte
from utils import janela_datas, padronizar_fato, salvar_parquet

logger = logging.getLogger("pipeline_bcb")

DEFAULT_CONFIG = {
    "url_base": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados",
    "output_filename": "fato_bcb",
    "timeout": 30,
    "tentativas": 3,
    "pausa_entre_series": 0.4,  # cortesia com a API pública
}


def _extrair_serie(codigo: str, dt_ini, dt_fim, cfg) -> pd.DataFrame:
    """Baixa uma série SGS no formato JSON e retorna o DataFrame cru."""
    url = cfg["url_base"].format(codigo=codigo)
    params = {
        "formato": "json",
        "dataInicial": dt_ini.strftime("%d/%m/%Y"),
        "dataFinal": dt_fim.strftime("%d/%m/%Y"),
    }
    ultimo_erro = None
    for tentativa in range(1, cfg["tentativas"] + 1):
        try:
            resp = requests.get(url, params=params, timeout=cfg["timeout"])
            resp.raise_for_status()
            return pd.DataFrame(resp.json())
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            logger.warning("Série %s tentativa %d falhou: %s", codigo, tentativa, e)
            time.sleep(1.5 * tentativa)
    raise RuntimeError(f"Falha ao extrair série SGS {codigo}: {ultimo_erro}")


def _transformar(bruto: pd.DataFrame, indicador_id: int) -> pd.DataFrame:
    """Tipagem: 'data' (dd/mm/aaaa) -> date, 'valor' (string vírgula) -> float."""
    if bruto.empty:
        return pd.DataFrame(columns=["data", "indicador_id", "valor"])
    df = bruto.copy()
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = pd.to_numeric(
        df["valor"].astype(str).str.replace(",", ".", regex=False), errors="coerce"
    )
    df["indicador_id"] = indicador_id
    return df


def executar(params=None) -> pd.DataFrame:
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    dt_ini, dt_fim = janela_datas()
    indicadores = por_fonte("BCB")
    logger.info("Iniciando extração BCB/SGS (%d séries)...", len(indicadores))

    partes = []
    for ind in indicadores:
        bruto = _extrair_serie(ind["codigo"], dt_ini, dt_fim, cfg)
        df = _transformar(bruto, ind["id"])
        logger.info("  %-22s -> %d obs", ind["nome"], len(df))
        partes.append(df)
        time.sleep(cfg["pausa_entre_series"])

    fato = padronizar_fato(pd.concat(partes, ignore_index=True))
    salvar_parquet(fato, cfg["output_filename"])
    return fato


if __name__ == "__main__":
    from utils import configurar_logging

    configurar_logging()
    executar()
