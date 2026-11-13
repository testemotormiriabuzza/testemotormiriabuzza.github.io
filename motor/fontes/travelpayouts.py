"""Travelpayouts (Aviasales Data API): menores preços por data encontrados por usuários nas últimas ~48 h.

Serve para varrer muitas rotas de graça. Os preços vêm de cache, então todo achado é conferido
antes de ir para o site.

Formato da resposta (prices_for_dates):
    {"success": true, "currency": "brl", "data": [{"origin", "destination", "origin_airport",
     "destination_airport", "price", "airline", "flight_number", "departure_at", "return_at",
     "transfers", "return_transfers", "duration", "link"}]}
"""

from . import ErroFonte, get_json

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def buscar_mes(origem, destino, mes, token, moeda="brl", mercado=None, limite=1000):
    """Passagens de ida e volta da rota. Com `mes` (AAAA-MM), só saídas naquele mês; com mes=None,
    as próximas datas de todos os meses (é a consulta que traz mais pares de datas, ~90 por rota)."""
    if not token:
        raise ErroFonte("TRAVELPAYOUTS_TOKEN não configurado (veja o README).", definitivo=True)
    params = {
        "origin": origem,
        "destination": destino,
        "departure_at": mes,
        "one_way": "false",
        "sorting": "price",
        "unique": "false",
        "currency": moeda,
        "market": mercado,
        "limit": limite,
        "token": token,
    }
    try:
        dados = get_json(API, params)
    except ErroFonte as e:
        # Se o limite pedido não for aceito, tenta com o limite menor que outros clientes usam.
        if limite > 30 and "limit" in str(e).lower():
            return buscar_mes(origem, destino, mes, token, moeda, mercado, limite=30)
        raise
    if not dados.get("success", False):
        raise ErroFonte(f"resposta sem sucesso: {dados.get('error') or dados}")
    moeda_resp = (dados.get("currency") or moeda).upper()
    return [b for b in (normalizar(t, moeda_resp) for t in dados.get("data") or []) if b]


def normalizar(t, moeda="BRL"):
    try:
        preco = float(t.get("price") or 0)
    except (TypeError, ValueError):
        return None
    ida = (t.get("departure_at") or "")[:10]
    volta = (t.get("return_at") or "")[:10]
    if preco <= 0 or not ida or not volta:
        return None
    link = (t.get("link") or "").strip()
    if link and not link.startswith("http"):
        link = "https://www.aviasales.com" + (link if link.startswith("/") else "/" + link)
    return {
        "origem": (t.get("origin") or "").upper(),
        "destino": (t.get("destination") or "").upper(),
        "aeroporto_origem": (t.get("origin_airport") or "").upper(),
        "aeroporto_destino": (t.get("destination_airport") or "").upper(),
        "ida": ida,
        "volta": volta,
        "hora_ida": (t.get("departure_at") or "")[11:16],
        "preco": round(preco, 2),
        "moeda": moeda,
        "cia": (t.get("airline") or "").upper(),
        "voo": str(t.get("flight_number") or ""),
        "escalas_ida": t.get("transfers"),
        "escalas_volta": t.get("return_transfers"),
        "duracao_min": t.get("duration"),
        "link_aviasales": link,
        "vendedor": t.get("gate") or "",
        "fonte": "travelpayouts",
    }
