"""
Testes das funções puras de transformação de cada pipeline e do contrato
de saída (padronizar_fato). Nenhum teste acessa rede ou banco.

Rodar:  pytest tests/ -v
"""
from datetime import date

import pandas as pd

import pipeline_bcb
import pipeline_focus
import pipeline_yahoo
from utils import padronizar_fato


# ---------------------------------------------------------------- BCB/SGS
def test_bcb_transformar_converte_data_e_virgula_decimal():
    bruto = pd.DataFrame(
        [
            {"data": "02/01/2026", "valor": "5,4321"},
            {"data": "03/01/2026", "valor": "5,50"},
        ]
    )
    df = pipeline_bcb._transformar(bruto, indicador_id=1)
    assert list(df["indicador_id"].unique()) == [1]
    assert df.loc[0, "valor"] == 5.4321
    assert df.loc[0, "data"] == pd.Timestamp("2026-01-02")


def test_bcb_transformar_dataframe_vazio():
    df = pipeline_bcb._transformar(pd.DataFrame(), indicador_id=1)
    assert df.empty
    assert list(df.columns) == ["data", "indicador_id", "valor"]


# ------------------------------------------------------------------ Yahoo
def _payload_yahoo(timestamps, closes):
    return {
        "chart": {
            "result": [
                {"timestamp": timestamps, "indicators": {"quote": [{"close": closes}]}}
            ]
        }
    }


def test_yahoo_transformar_aplica_fator_e_normaliza_data():
    # 2026-01-02 15:30 UTC -> deve virar a data 2026-01-02
    payload = _payload_yahoo([1767367800], [1050.0])
    ind = {"id": 12, "fator": 0.01}  # Soja: centavos/bushel -> US$/bushel
    df = pipeline_yahoo._transformar(payload, ind)
    assert df.loc[0, "valor"] == 10.50
    assert df.loc[0, "data"] == pd.Timestamp("2026-01-02")


def test_yahoo_transformar_ignora_closes_nulos():
    payload = _payload_yahoo([1767367800, 1767454200], [None, 100.0])
    df = pipeline_yahoo._transformar(payload, {"id": 8})
    assert len(df) == 1
    assert df.iloc[0]["valor"] == 100.0


def test_yahoo_transformar_payload_invalido_retorna_vazio():
    df = pipeline_yahoo._transformar({"chart": {"result": None}}, {"id": 8})
    assert df.empty
    assert list(df.columns) == ["data", "indicador_id", "valor"]


# ------------------------------------------------------------------ Focus
def test_focus_transformar_renomeia_e_tipa():
    bruto = pd.DataFrame(
        [
            {"Indicador": "IPCA", "Data": "2026-06-26", "DataReferencia": "2026", "Mediana": 4.32},
        ]
    )
    df = pipeline_focus._transformar(bruto, indicador_id=16)
    assert df.loc[0, "valor"] == 4.32
    assert df.loc[0, "data"] == pd.Timestamp("2026-06-26")
    assert df.loc[0, "indicador_id"] == 16


def test_focus_transformar_sem_coluna_data_retorna_vazio():
    df = pipeline_focus._transformar(pd.DataFrame([{"x": 1}]), indicador_id=16)
    assert df.empty


def test_focus_montar_url_limita_janela_e_mantem_dolar_literal():
    url = pipeline_focus._montar_url(
        "IPCA", 2026, date(2026, 1, 1), date(2026, 12, 31),
        pipeline_focus.DEFAULT_CONFIG,
    )
    assert "$filter=" in url          # '$' precisa ficar literal (Olinda)
    assert "Data%20ge%20'2026-01-01'" in url
    assert "Data%20le%20'2026-12-31'" in url
    assert "DataReferencia%20eq%20'2026'" in url


# --------------------------------------------------- contrato padronizar_fato
def test_padronizar_fato_remove_nulos_e_duplicatas():
    df = pd.DataFrame(
        {
            "data": ["2026-01-02", "2026-01-02", "2026-01-03"],
            "indicador_id": [1, 1, 1],
            "valor": [5.40, 5.45, None],  # duplicata (mantém a última) + nulo
        }
    )
    fato = padronizar_fato(df)
    assert len(fato) == 1
    assert fato.loc[0, "valor"] == 5.45
    assert fato.loc[0, "data"] == date(2026, 1, 2)
    assert fato["indicador_id"].dtype == "int64"
