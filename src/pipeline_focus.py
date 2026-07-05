"""
Pipeline especialista — Boletim Focus (BCB / API Olinda Expectativas).

Captura a SÉRIE histórica da mediana das expectativas de mercado anuais
para IPCA, PIB Total, Câmbio e Selic — uma observação por data de coleta do
Focus dentro da janela configurada (ETL_DIAS_HISTORICO). A data do fato é a
data da coleta Focus.

Semântica "ano corrente": cada coleta usa como ano-referência o ano-calendário
DA PRÓPRIA COLETA (coletas de 2026 -> expectativa para 2026; coletas de 2027 ->
2027). Assim, uma janela que cruza a virada do ano extrai cada trecho com o
ano-referência correto e a recarga nunca sobrescreve o histórico do ano
anterior com referência errada.

Doc: https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/aplicacao
"""
import logging
import time
from datetime import date
from urllib.parse import quote

import pandas as pd
import requests

from config_indicadores import por_fonte
from utils import janela_datas, padronizar_fato, salvar_parquet

logger = logging.getLogger("pipeline_focus")

DEFAULT_CONFIG = {
    "url_base": (
        "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
        "ExpectativasMercadoAnuais"
    ),
    "output_filename": "fato_focus",
    "timeout": 40,
    "tentativas": 3,
}


def _montar_url(nome_indicador: str, ano: int, dt_ini, dt_fim, cfg) -> str:
    """
    Monta a URL OData. O serviço Olinda exige o '$' LITERAL nos parâmetros
    ($top, $filter...). O requests encodaria como %24 e a API retornaria 400,
    por isso construímos a query string manualmente.

    Traz a SÉRIE histórica: todas as coletas (base 30 dias) do ano-referência
    dentro de [dt_ini, dt_fim], ordenadas por data.
    """
    filtro = (
        f"Indicador eq '{nome_indicador}' "
        f"and DataReferencia eq '{ano}' and baseCalculo eq 0 "
        f"and Data ge '{dt_ini.strftime('%Y-%m-%d')}' "
        f"and Data le '{dt_fim.strftime('%Y-%m-%d')}'"
    )
    query = (
        "$top=10000&$format=json&$orderby=Data"
        "&$select=Indicador,Data,DataReferencia,Mediana"
        f"&$filter={filtro}"
    )
    return cfg["url_base"] + "?" + quote(query, safe="$&=,'")


def _extrair_indicador(nome_indicador: str, ano: int, dt_ini, dt_fim, cfg) -> pd.DataFrame:
    """Série histórica das medianas (base 30 dias) no ano-referência informado."""
    url = _montar_url(nome_indicador, ano, dt_ini, dt_fim, cfg)
    ultimo_erro = None
    for tentativa in range(1, cfg["tentativas"] + 1):
        try:
            resp = requests.get(url, timeout=cfg["timeout"])
            resp.raise_for_status()
            return pd.DataFrame(resp.json().get("value", []))
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            logger.warning("Focus %s tentativa %d falhou: %s", nome_indicador, tentativa, e)
            time.sleep(1.5 * tentativa)
    raise RuntimeError(f"Falha ao extrair Focus {nome_indicador}: {ultimo_erro}")


def _transformar(bruto: pd.DataFrame, indicador_id: int) -> pd.DataFrame:
    if bruto.empty or "Data" not in bruto.columns:
        return pd.DataFrame(columns=["data", "indicador_id", "valor"])
    df = bruto.rename(columns={"Data": "data", "Mediana": "valor"})
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df["indicador_id"] = indicador_id
    return df


def executar(params=None) -> pd.DataFrame:
    cfg = {**DEFAULT_CONFIG, **(params or {})}
    dt_ini, dt_fim = janela_datas()
    anos = list(range(dt_ini.year, dt_fim.year + 1))
    indicadores = por_fonte("FOCUS")
    logger.info(
        "Iniciando extração Focus (%d indicadores, anos-referência=%s)...",
        len(indicadores), anos,
    )

    partes = []
    for ind in indicadores:
        total = 0
        # Um request por ano-calendário coberto pela janela, cada um com o
        # ano-referência corrente daquele trecho.
        for ano in anos:
            ini = max(dt_ini, date(ano, 1, 1))
            fim = min(dt_fim, date(ano, 12, 31))
            bruto = _extrair_indicador(ind["codigo"], ano, ini, fim, cfg)
            df = _transformar(bruto, ind["id"])
            total += len(df)
            partes.append(df)
            time.sleep(0.3)
        logger.info("  %-30s -> %d obs", ind["nome"], total)

    fato = padronizar_fato(pd.concat(partes, ignore_index=True))
    salvar_parquet(fato, cfg["output_filename"])
    return fato


if __name__ == "__main__":
    from utils import configurar_logging

    configurar_logging()
    executar()
