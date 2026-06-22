"""
Orquestrador Principal

Substitui a lógica do Airflow. Executa sequencialmente todos os módulos de 
extração (ETLs) do IPCA e metas de inflação.
"""
import logging
import os
import sys
import traceback
from datetime import datetime

# Garante que os módulos ETL em src/ sejam encontrados,
# independentemente do diretório de onde o script é executado.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importa os módulos ETL locais
import ipca_serie_historica
import ipca_7060_grupos
import ipca_7060_rm_municipios
import ipca_7060_hierarquia
import meta_inflacao

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuração global compartilhada pelos módulos (ex: mesma pasta de destino)
CONFIG_GLOBAL = {
    "dest_path": "./dados_ipca"
}

ETLS_ATIVOS = [
    ("Série Histórica (1737)", ipca_serie_historica.executar),
    ("Grupos Nacionais (7060)", ipca_7060_grupos.executar),
    ("RM e Municípios (7060)", ipca_7060_rm_municipios.executar),
    ("Hierarquia Completa (7060)", ipca_7060_hierarquia.executar),
    ("Meta de Inflação (SGS/BCB)", meta_inflacao.executar),
]

def rodar_pipeline():
    logger.info("="*50)
    logger.info("INICIANDO PIPELINE COMPLETO DE DADOS - %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("="*50)
    
    sucessos = 0
    falhas = 0
    
    for nome, func_executar in ETLS_ATIVOS:
        logger.info("\n>>> Iniciando rotina: %s", nome)
        try:
            # Chama a função passando as configurações customizadas
            caminho_gerado = func_executar(CONFIG_GLOBAL)
            logger.info(">>> Rotina %s concluída com sucesso. [%s]", nome, caminho_gerado)
            sucessos += 1
        except Exception as e:
            logger.error(">>> FALHA na rotina %s: %s", nome, e)
            logger.error(traceback.format_exc())
            falhas += 1
            
    logger.info("\n" + "="*50)
    logger.info("RESUMO DA EXECUÇÃO")
    logger.info("Sucessos: %d | Falhas: %d", sucessos, falhas)
    logger.info("="*50)

if __name__ == "__main__":
    rodar_pipeline()
