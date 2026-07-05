# Painel Macroeconômico — ETL

Pipeline de ingestão diária de indicadores macroeconômicos para um painel
executivo (com foco em agronegócio). Segue o template **ETL Minimalista em
Python**: sem orquestradores pesados, formato `parquet` na camada local e carga
em **PostgreSQL** (modelo estrela) para consumo no Power BI.

```
APIs Públicas  ->  Python ETL  ->  parquet (local)  ->  PostgreSQL  ->  Power BI
   (BCB, Yahoo,       (src/)        dados_processados/   schema           (07h00)
    Focus)                                               macroeconomia
```

## Indicadores cobertos (18)

| Categoria   | Indicadores | Fonte |
|-------------|-------------|-------|
| **Brasil**  | Dólar (PTAX), Selic Meta, CDI | BCB/SGS |
| **Brasil**  | Ibovespa | Yahoo (`^BVSP`) |
| **Global**  | DXY, Treasury 10a, S&P 500, Nasdaq, Brent | Yahoo |
| **Commodity** | WTI, Soja, Milho, Trigo, Minério de Ferro | Yahoo |
| **Focus**   | IPCA, PIB, Câmbio, Selic (ano corrente) | BCB/Olinda |

> Soja/Milho/Trigo do Yahoo vêm em centavos/bushel; o ETL converte para
> **US$/bushel** (`fator: 0.01`) automaticamente.
> O Focus traz a **série histórica** das medianas (uma por data de coleta) dentro
> da janela `ETL_DIAS_HISTORICO`, não apenas o último valor. O ano-referência de
> cada coleta é o **ano da própria coleta** (coletas de 2026 → expectativa para
> 2026), então janelas que cruzam a virada do ano permanecem consistentes.

## Estrutura

```
macroeconomia/
├── .env                      # credenciais e parâmetros (NÃO versionar)
├── .env.example              # template
├── requirements.txt
├── run_etl.sh / run_etl.ps1  # execução (Linux/cron  e  Windows/Agendador)
├── sql/
│   └── schema_macroeconomia.sql   # DDL idempotente do modelo estrela
└── src/
    ├── config_indicadores.py # CATÁLOGO central (fonte única da verdade)
    ├── utils.py              # .env, parquet, engine PostgreSQL
    ├── pipeline_bcb.py       # extrator BCB/SGS
    ├── pipeline_yahoo.py     # extrator Yahoo Finance (chart API)
    ├── pipeline_focus.py     # extrator Boletim Focus (Olinda)
    ├── load_postgres.py      # carga em PostgreSQL (UPSERT em lote)
    └── orquestrador.py       # maestro: extrai tudo + carrega
```

## Modelo dimensional (schema `macroeconomia`)

- **dim_data** (`data_id` YYYYMMDD, data, ano, mês, dia, trimestre, nome_mês, dia_semana)
- **dim_indicador** (`indicador_id`, nome, categoria, unidade, fonte, codigo)
- **fat_macroeconomia** (`data_id`, `indicador_id`, valor) — PK composta
- **vw_macroeconomia** — view desnormalizada pronta para o BI

## Como rodar

```bash
# 1. ambiente
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux
pip install -r requirements.txt

# 2. configurar credenciais
cp .env.example .env            # e preencher PG_PASSWORD etc.

# 3. executar o pipeline completo (extração + carga)
python src/orquestrador.py
```

Cada extrator também roda isolado para teste:
`python src/pipeline_bcb.py`, `python src/pipeline_yahoo.py`, etc.

A carga pode ser reexecutada sozinha (idempotente) sobre os parquets já gerados:
`python src/load_postgres.py`.

## Agendamento diário (07h00)

**Linux (cron):**
```bash
0 7 * * * /caminho/macroeconomia/run_etl.sh >> /caminho/macroeconomia/log.txt 2>&1
```

**Windows (Agendador de Tarefas):** acione `run_etl.ps1` diariamente às 07:00
(`powershell -ExecutionPolicy Bypass -File C:\...\macroeconomia\run_etl.ps1`).

## Decisões de projeto

- **Sem `yfinance`**: usamos a *chart API* pública do Yahoo via `requests`,
  mantendo o projeto leve (princípio KISS).
- **Extração desacoplada da carga**: se o banco/rede cair, os parquets já estão
  salvos; basta rerodar `load_postgres.py`.
- **UPSERT em lote** (`execute_values`): uma ida ao banco para milhares de linhas,
  essencial em conexão remota de alta latência. Recarga diária não duplica dados.
- **Catálogo central** (`config_indicadores.py`): adicionar um indicador = uma
  linha; o `indicador_id` é a chave de negócio estável do histórico.

## Adicionando um novo indicador

1. Acrescente uma linha em `INDICADORES` (em `config_indicadores.py`) com o
   próximo `id` livre, a `fonte` e o `codigo`/ticker.
2. Rode `python src/orquestrador.py`. O extrator da fonte correspondente já o
   captura e a dimensão é atualizada automaticamente.
