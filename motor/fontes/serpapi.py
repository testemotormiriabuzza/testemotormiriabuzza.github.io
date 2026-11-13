"""SerpApi (Google Flights): confere um achado com o preço atual e a faixa de preço típico do Google.

Campos usados da resposta (engine=google_flights, type=1 ida e volta):
    best_flights[].price, other_flights[].price
    price_insights: lowest_price, price_level ("low" / "typical" / "high"), typical_price_range [min, max]
O plano grátis tem 250 buscas por mês.
"""

from . import ErroFonte, get_json

API = "https://serpapi.com/search"


def conferir(aeroportos_origem, aeroportos_destino, ida, volta, chave, moeda="BRL"):
    if not chave:
        raise ErroFonte("SERPAPI_KEY não configurada.", definitivo=True)
    params = {
        "engine": "google_flights",
        "departure_id": aeroportos_origem,
        "arrival_id": aeroportos_destino,
        "outbound_date": ida,
        "return_date": volta,
        "type": 1,
        "currency": moeda,
        "gl": "br",
        "api_key": chave,
    }
    dados = get_json(API, params, timeout=60)
    if dados.get("error"):
        raise ErroFonte(f"SerpApi: {dados['error']}")
    precos = []
    for grupo in ("best_flights", "other_flights"):
        for item in dados.get(grupo) or []:
            try:
                if item.get("price"):
                    precos.append(float(item["price"]))
            except (TypeError, ValueError):
                continue
    insights = dados.get("price_insights") or {}
    menor = min(precos) if precos else insights.get("lowest_price")
    faixa = insights.get("typical_price_range")
    if not (isinstance(faixa, list) and len(faixa) == 2):
        faixa = None
    return {
        "menor_preco": float(menor) if menor else None,
        "nivel": insights.get("price_level"),
        "faixa_tipica": faixa,
    }
