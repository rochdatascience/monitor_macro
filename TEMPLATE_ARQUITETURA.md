# Template de Arquitetura: ETL Minimalista em Python

Este documento descreve o padrão de arquitetura utilizado neste projeto, projetado para ser **simples, escalável e livre de dependências pesadas** (como Apache Airflow, Spark ou Trino). Ele é ideal para projetos de ingestão de dados de APIs, bancos relacionais ou web scraping, com volumes de dados pequenos a médios.

---

## 1. Princípios da Arquitetura

1. **Simplicidade (KISS)**: Sem ferramentas complexas de orquestração. O agendamento é feito pelo Sistema Operacional (`cron`) e a execução por um script Python central.
2. **Eficiência de Armazenamento**: Uso do formato `.parquet`, que é colunar, tipado e altamente compactado, ideal para consumo em ferramentas de BI (Power BI, Metabase).
3. **Desacoplamento**: Cada fonte de dados tem seu próprio script contendo lógicas puras de extração e transformação.
4. **Segurança**: Credenciais nunca ficam no código, sendo injetadas via `.env`.

---

## 2. Estrutura de Diretórios Recomendada

Para iniciar um novo projeto, replique a seguinte estrutura:

```text
meu_novo_projeto_etl/
├── .gitignore              # Arquivos ignorados pelo controle de versão (ex: .env, dados_ipca/)
├── .env.example            # Template de variáveis (ex: MINIO_ENDPOINT)
├── .env                    # Variáveis locais reais (ignorado no git)
├── requirements.txt        # pandas, pyarrow, python-dotenv, boto3, requests
├── run_etl.sh              # Script bash para ativar ambiente e rodar o pipeline
├── README.md               # Documentação do negócio
└── src/
    ├── pipeline_a.py       # Script especialista na Fonte A
    ├── pipeline_b.py       # Script especialista na Fonte B
    ├── upload_storage.py   # Módulo genérico para envio ao Data Lake (S3/MinIO)
    └── orquestrador.py     # Ponto de entrada que chama os pipelines
```

---

## 3. Padrão de Código (Scripts Especialistas)

Cada arquivo dentro de `src/` (ex: `pipeline_a.py`) deve seguir um padrão estrutural rigoroso:

### A. Configurações no Topo
Use um dicionário `DEFAULT_CONFIG` no início do arquivo para que parâmetros possam ser alterados facilmente.

```python
DEFAULT_CONFIG = {
    "url_api": "https://api.exemplo.com/dados",
    "output_filename": "dados_vendas",
    "dest_path": "./dados_processados"
}
```

### B. Separação de Responsabilidades (Funções)
Divida o processo em 3 funções claras:

1. `_extrair()`: Apenas faz requisições (com try/except e retries) e retorna o dado bruto (JSON, CSV ou DataFrame cru).
2. `_transformar(dados_brutos)`: Aplica tipagem (converte datas, floats), renomeia colunas, limpa nulos e faz pivotagem. Retorna um DataFrame pronto.
3. `executar(params=None)`: A função pública que o orquestrador vai chamar. Ela junta a extração, a transformação e salva o `.parquet`.

### C. Logging Nativo
Nunca use `print()`. Use a biblioteca `logging` do Python para rastreabilidade:

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

logger.info("Iniciando extração...")
```

---

## 4. O Orquestrador (`orquestrador.py`)

A função do orquestrador é ser o "Maestro". Ele não sabe *como* extrair os dados, ele apenas sabe *quem* chamar.

```python
import logging
import pipeline_a
import pipeline_b

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

ETLS_ATIVOS = [
    ("Vendas (Fonte A)", pipeline_a.executar),
    ("Clientes (Fonte B)", pipeline_b.executar),
]

def rodar_pipeline():
    logging.info("INICIANDO PIPELINE GERAL")
    for nome, funcao_executar in ETLS_ATIVOS:
        try:
            funcao_executar()
            logging.info(f"Sucesso: {nome}")
        except Exception as e:
            logging.error(f"Erro em {nome}: {e}")

if __name__ == "__main__":
    rodar_pipeline()
```

---

## 5. Carga e Armazenamento (Data Lake)

1. **Localmente**: O orquestrador salva tudo em uma pasta temporária (ex: `./dados_processados`).
2. **Cloud/S3**: Um script separado (`upload_storage.py`) varre essa pasta e envia tudo para um bucket S3/MinIO usando a biblioteca `boto3`.

*Por que separar o upload?* 
Se a internet cair ou o S3 estiver fora do ar, o processamento (que pode ter demorado horas) já foi feito e os dados estão salvos localmente. Basta rodar o script de upload novamente mais tarde.

---

## 6. Agendamento (Deploy)

Em produção (como um servidor Ubuntu), você não precisa de Airflow. Um simples script Bash e o Cron resolvem 99% dos casos:

1. Crie o `run_etl.sh`:
   ```bash
   cd /caminho/do/projeto
   python3 src/orquestrador.py
   python3 src/upload_storage.py
   ```
2. Agende no `crontab -e`:
   ```bash
   # Roda todos os dias ao meio-dia
   0 12 * * * /caminho/do/projeto/run_etl.sh >> log.txt 2>&1
   ```
