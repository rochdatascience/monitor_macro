"""
Orquestrador — o "maestro" do pipeline macroeconômico.

Não sabe COMO extrair; apenas sabe QUEM chamar e em que ordem:
  1) roda cada extrator (gera parquet local em ./dados_processados)
  2) carrega tudo no PostgreSQL (schema macroeconomia)

A falha de um extrator é registrada e NÃO interrompe os demais.
"""
import logging
import sys

import pipeline_bcb
import pipeline_focus
import pipeline_yahoo
import load_postgres
from utils import configurar_logging

configurar_logging()
logger = logging.getLogger("orquestrador")

EXTRATORES = [
    ("BCB/SGS (Dólar, Selic, CDI)", pipeline_bcb.executar),
    ("Yahoo Finance (índices/commodities)", pipeline_yahoo.executar),
    ("Boletim Focus", pipeline_focus.executar),
]


def rodar_extracao() -> int:
    logger.info("=== INICIANDO EXTRAÇÃO ===")
    falhas = 0
    for nome, executar in EXTRATORES:
        try:
            executar()
            logger.info("Sucesso: %s", nome)
        except Exception as e:  # noqa: BLE001
            falhas += 1
            logger.error("Erro em %s: %s", nome, e)
    return falhas


def rodar_carga():
    logger.info("=== INICIANDO CARGA POSTGRES ===")
    load_postgres.executar()


def rodar_pipeline():
    falhas = rodar_extracao()
    rodar_carga()
    logger.info("=== PIPELINE CONCLUÍDO (%d extrator(es) com falha) ===", falhas)
    # Falha parcial não derruba o build, mas sinaliza no código de saída.
    return 0 if falhas == 0 else 2


if __name__ == "__main__":
    sys.exit(rodar_pipeline())
