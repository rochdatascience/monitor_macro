"""
Catálogo central de indicadores (fonte única da verdade).

Cada indicador tem um `id` estável que alimenta a dimensão `dim_indicador`.
Os pipelines especialistas filtram este catálogo pela coluna `fonte` e usam
o campo `codigo` para saber o que buscar em cada API.

NUNCA reordene/reaproveite ids existentes: o id é a chave de negócio que liga
o histórico em `fat_macroeconomia`. Para um novo indicador, use o próximo id livre.
"""

# fontes: "BCB" (SGS), "YAHOO" (chart API), "FOCUS" (Olinda)
INDICADORES = [
    # ----------------- Cenário Brasil -----------------
    {"id": 1,  "nome": "Dólar (PTAX venda)", "categoria": "Brasil",       "unidade": "R$",            "fonte": "BCB",   "codigo": "1"},
    {"id": 2,  "nome": "Selic Meta",          "categoria": "Brasil",       "unidade": "% a.a.",        "fonte": "BCB",   "codigo": "432"},
    {"id": 3,  "nome": "CDI",                 "categoria": "Brasil",       "unidade": "% a.a.",        "fonte": "BCB",   "codigo": "4389"},
    {"id": 4,  "nome": "Ibovespa",            "categoria": "Brasil",       "unidade": "pontos",        "fonte": "YAHOO", "codigo": "^BVSP"},

    # --------------- Cenário Internacional ---------------
    {"id": 6,  "nome": "DXY (Dollar Index)",  "categoria": "Global",       "unidade": "índice",        "fonte": "YAHOO", "codigo": "DX-Y.NYB"},
    {"id": 7,  "nome": "Treasury 10 anos",    "categoria": "Global",       "unidade": "% a.a.",        "fonte": "YAHOO", "codigo": "^TNX"},
    {"id": 8,  "nome": "S&P 500",             "categoria": "Global",       "unidade": "pontos",        "fonte": "YAHOO", "codigo": "^GSPC"},
    {"id": 9,  "nome": "Nasdaq",              "categoria": "Global",       "unidade": "pontos",        "fonte": "YAHOO", "codigo": "^IXIC"},
    {"id": 10, "nome": "Brent",               "categoria": "Global",       "unidade": "US$/barril",    "fonte": "YAHOO", "codigo": "BZ=F"},

    # ------------------- Commodities -------------------
    {"id": 11, "nome": "Petróleo WTI",        "categoria": "Commodity",    "unidade": "US$/barril",    "fonte": "YAHOO", "codigo": "CL=F"},
    {"id": 12, "nome": "Soja",                "categoria": "Commodity",    "unidade": "US$/bushel",    "fonte": "YAHOO", "codigo": "ZS=F", "fator": 0.01},
    {"id": 13, "nome": "Milho",               "categoria": "Commodity",    "unidade": "US$/bushel",    "fonte": "YAHOO", "codigo": "ZC=F", "fator": 0.01},
    {"id": 14, "nome": "Trigo",               "categoria": "Commodity",    "unidade": "US$/bushel",    "fonte": "YAHOO", "codigo": "ZW=F", "fator": 0.01},
    {"id": 15, "nome": "Minério de Ferro",    "categoria": "Commodity",    "unidade": "US$/ton",       "fonte": "YAHOO", "codigo": "TIO=F"},

    # ------------ Boletim Focus (expectativas) ------------
    {"id": 16, "nome": "Focus IPCA (ano corrente)",   "categoria": "Focus", "unidade": "%",      "fonte": "FOCUS", "codigo": "IPCA"},
    {"id": 17, "nome": "Focus PIB Total (ano corrente)", "categoria": "Focus", "unidade": "%",   "fonte": "FOCUS", "codigo": "PIB Total"},
    {"id": 18, "nome": "Focus Câmbio (ano corrente)", "categoria": "Focus", "unidade": "R$",     "fonte": "FOCUS", "codigo": "Câmbio"},
    {"id": 19, "nome": "Focus Selic (ano corrente)",  "categoria": "Focus", "unidade": "% a.a.", "fonte": "FOCUS", "codigo": "Selic"},
]


def por_fonte(fonte: str):
    """Retorna a lista de indicadores de uma determinada fonte."""
    return [ind for ind in INDICADORES if ind["fonte"] == fonte]


def mapa_por_id():
    return {ind["id"]: ind for ind in INDICADORES}
