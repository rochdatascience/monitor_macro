"""
Pipeline especialista — Yahoo Finance (chart API pública, sem dependências pesadas).

Indicadores: Ibovespa, DXY, Treasury 10a, S&P 500, Nasdaq, Brent, WTI,
Soja, Milho, Trigo e Minério de Ferro.

Endpoint: https://query1.finance.yahoo.com/v8/finance/chart/{symbol}
Retorna fechamento diário ajustado. Símbolos com falha são apenas avisados
(ex.: TIO=F pode ficar indisponível) e não derrubam o pipeline inteiro.
"""
import logging
import time

import pandas as pd
import requests

from config_indicadores import por_fonte
from utils import dias_historico, padronizar_fato, salvar_parquet

logger = logging.getLogger("pipeline_yahoo")

DEFAULT_CONFIG = {
    "url_base": "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
    "output_filename": "fato_yahoo",
    "timeout": 30,
    "tentativas": 3,
    "interval": "1d",
    "headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    },
}


def _range_yahoo() -> str:
    """Converte a janela em dias no parâmetro 'range' aceito pela API."""
    dias = dias_historico()
    if dias <= 35:
        return "1mo"
    if dias <= 100:
        return "3mo"
    if dias <= 200:
        return "6mo"
    if dias <= 400:
        return "1y"
    if dias <= 800:
        return "2y"
    return "5y"


def _extrair_symbol(symbol: str, cfg) -> dict:
    url = cfg["url_base"].format(symbol=symbol)
    params = {"range": _range_yahoo(), "interval": cfg["interval"]}
    ultimo_erro = None
    for tentativa in range(1, cfg["tentativas"] + 1):
        try:
            resp = requests.get(
                url, params=params, headers=cfg["headers"], timeout=cfg["timeout"]
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            logger.warning("Symbol %s tentativa %d falhou: %s", symbol, tentativa, e)
            time.sleep(1.5 * tentativa)
    raise RuntimeError(f"Falha ao extrair {symbol}: {ultimo_erro}")


def _transformar(payload: dict, ind: dict) -> pd.DataFrame:
    try:
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return pd.DataFrame(columns=["data", "indicador_id", "valor"])

    df = pd.DataFrame({"ts": timestamps, "valor": closes}).dropna(subset=["valor"])
    df["data"] = pd.to_datetime(df["ts"], unit="s").dt.normalize()
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce") * ind.get("fator", 1.0)
    df["indicador_id"] = ind["id"]
    return df[["data", "indicador_id", "valor"]]


def executar(params=None) -> pd.DataFrame:
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    indicadores = por_fonte("YAHOO")
    logger.info("Iniciando extração Yahoo Finance (%d símbolos)...", len(indicadores))

    partes = []
    for ind in indicadores:
        try:
            payload = _extrair_symbol(ind["codigo"], cfg)
            df = _transformar(payload, ind)
            logger.info("  %-22s (%-9s) -> %d obs", ind["nome"], ind["codigo"], len(df))
            partes.append(df)
        except Exception as e:  # noqa: BLE001
            logger.error("  %-22s FALHOU e foi ignorado: %s", ind["nome"], e)
        time.sleep(0.3)

    fato = padronizar_fato(pd.concat(partes, ignore_index=True))
    salvar_parquet(fato, cfg["output_filename"])
    return fato


if __name__ == "__main__":
    from utils import configurar_logging

    configurar_logging()
    executar()
