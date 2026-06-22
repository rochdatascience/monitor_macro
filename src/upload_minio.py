import os
import sys
import boto3
from botocore.exceptions import ClientError
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

# Configurações do MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")
DIRETORIO_DADOS = "./dados_ipca"

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )

def criar_bucket(s3_client, bucket_name):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logging.info(f"O bucket '{bucket_name}' já existe.")
    except ClientError as e:
        # head_bucket pode falhar por bucket inexistente (404) ou por
        # erro de credencial/permissão (403). Só criamos no caso de 404.
        codigo = e.response.get("Error", {}).get("Code", "")
        if codigo in ("404", "NoSuchBucket"):
            logging.info(f"Criando o bucket '{bucket_name}'...")
            s3_client.create_bucket(Bucket=bucket_name)
            logging.info(f"Bucket '{bucket_name}' criado com sucesso.")
        else:
            logging.error(
                f"Não foi possível acessar o bucket '{bucket_name}' (código {codigo}). "
                "Verifique endpoint e credenciais."
            )
            raise

def fazer_upload_arquivos(s3_client, bucket_name, diretorio):
    """Faz upload dos .parquet e retorna o número de falhas."""
    if not os.path.exists(diretorio):
        logging.error(f"O diretório {diretorio} não existe.")
        return 1

    arquivos = [f for f in os.listdir(diretorio) if f.endswith('.parquet')]

    if not arquivos:
        logging.warning("Nenhum arquivo .parquet encontrado para upload.")
        return 0

    falhas = 0
    for arquivo in arquivos:
        caminho_local = os.path.join(diretorio, arquivo)
        caminho_s3 = arquivo # Nome do arquivo no bucket

        logging.info(f"Fazendo upload de '{arquivo}'...")
        try:
            s3_client.upload_file(caminho_local, bucket_name, caminho_s3)
            logging.info(f"Upload de '{arquivo}' concluído com sucesso.")
        except Exception as e:
            logging.error(f"Erro ao fazer upload de '{arquivo}': {e}")
            falhas += 1

    return falhas

def main():
    logging.info("Iniciando processo de upload para o MinIO...")
    s3_client = get_s3_client()

    criar_bucket(s3_client, BUCKET_NAME)
    falhas = fazer_upload_arquivos(s3_client, BUCKET_NAME, DIRETORIO_DADOS)

    if falhas:
        logging.error("Processo finalizado com %d falha(s) de upload.", falhas)
        sys.exit(1)

    logging.info("Processo finalizado!")

if __name__ == "__main__":
    main()
