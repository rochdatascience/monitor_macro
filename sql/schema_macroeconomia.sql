-- ============================================================================
-- Esquema dimensional do Painel Macroeconômico
-- Banco: PostgreSQL  | Schema: macroeconomia
-- Modelo estrela: fato (fat_macroeconomia) + dimensões (dim_data, dim_indicador)
-- Script idempotente: pode rodar quantas vezes quiser.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS macroeconomia;

-- ----------------------------------------------------------------------------
-- Dimensão Tempo
-- data_id no formato YYYYMMDD (ex.: 20260621)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS macroeconomia.dim_data (
    data_id     INTEGER     PRIMARY KEY,
    data        DATE        NOT NULL,
    ano         SMALLINT    NOT NULL,
    mes         SMALLINT    NOT NULL,
    dia         SMALLINT    NOT NULL,
    trimestre   SMALLINT    NOT NULL,
    nome_mes    VARCHAR(20) NOT NULL,
    dia_semana  SMALLINT    NOT NULL   -- 0=segunda ... 6=domingo
);

-- ----------------------------------------------------------------------------
-- Dimensão Indicador
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS macroeconomia.dim_indicador (
    indicador_id INTEGER      PRIMARY KEY,
    nome         VARCHAR(80)  NOT NULL,
    categoria    VARCHAR(30)  NOT NULL,   -- Brasil | Global | Commodity | Focus
    unidade      VARCHAR(20)  NOT NULL,
    fonte        VARCHAR(20)  NOT NULL,   -- BCB | YAHOO | FOCUS
    codigo       VARCHAR(40)  NOT NULL    -- código/ticker na fonte de origem
);

-- ----------------------------------------------------------------------------
-- Fato Macroeconomia (granularidade: 1 valor por data x indicador)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS macroeconomia.fat_macroeconomia (
    data_id      INTEGER          NOT NULL REFERENCES macroeconomia.dim_data (data_id),
    indicador_id INTEGER          NOT NULL REFERENCES macroeconomia.dim_indicador (indicador_id),
    valor        DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (data_id, indicador_id)
);

CREATE INDEX IF NOT EXISTS ix_fato_indicador ON macroeconomia.fat_macroeconomia (indicador_id);
CREATE INDEX IF NOT EXISTS ix_fato_data      ON macroeconomia.fat_macroeconomia (data_id);

-- ----------------------------------------------------------------------------
-- View de apoio ao BI: fato já desnormalizado com nome/categoria/unidade e data
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW macroeconomia.vw_macroeconomia AS
SELECT
    d.data,
    d.ano,
    d.mes,
    i.indicador_id,
    i.nome              AS indicador,
    i.categoria,
    i.unidade,
    i.fonte,
    f.valor
FROM macroeconomia.fat_macroeconomia f
JOIN macroeconomia.dim_data       d ON d.data_id = f.data_id
JOIN macroeconomia.dim_indicador  i ON i.indicador_id = f.indicador_id;
