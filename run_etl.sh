#!/bin/bash

# Acessa o diretório do projeto (ajuste o caminho de acordo com onde o projeto está no Ubuntu)
# cd /caminho/para/o/seu/projeto/etl

# Carrega as variáveis de ambiente (opcional se você usar python-dotenv no código, mas boa prática)
# set -a
# source .env
# set +a

# Ativa o ambiente virtual (descomente e ajuste se estiver usando um)
# source venv/bin/activate

echo "Iniciando processo ETL do IPCA..."

# Executa o orquestrador (Extração e Transformação local)
python3 src/orquestrador.py

# Verifica se o orquestrador rodou com sucesso
if [ $? -eq 0 ]; then
    echo "ETL finalizado com sucesso. Iniciando upload para o MinIO..."
    # Executa o script de upload para o MinIO
    python3 src/upload_minio.py

    if [ $? -eq 0 ]; then
        echo "Upload para o MinIO concluído com sucesso!"
    else
        echo "Erro durante o upload para o MinIO."
    fi

    echo "Iniciando carga das tabelas no PostgreSQL..."
    # Executa o script de carga para o PostgreSQL
    python3 src/upload_postgres.py

    if [ $? -eq 0 ]; then
        echo "Carga no PostgreSQL concluída com sucesso!"
    else
        echo "Erro durante a carga no PostgreSQL."
    fi
else
    echo "Erro durante a execução do orquestrador. Upload cancelado."
fi
