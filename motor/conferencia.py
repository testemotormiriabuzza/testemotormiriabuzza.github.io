"""Conferência dos achados no Google Flights (SerpApi), dentro do teto de buscas do plano grátis.

Veredito:
- "confirmado": o Google ainda mostra um preço até 15% acima do achado E diz que o preço está baixo
  (price_level "low" ou abaixo da faixa típica).
- "preco_mudou": o menor preço do Google está mais de 15% acima do achado.
- "nao_confirmado": o preço bate, mas o Google não considera baixo.
- "sem_resposta": o Google não devolveu preço para essas datas.
Sem SERPAPI_KEY, nada é conferido aqui e o achado fica "a conferir" para conferência manual.
"""

import json
from urllib.parse import quote

from .config import PASTA_DADOS
from .fontes import ErroFonte
from .fontes import serpapi

ARQUIVO_USO = PASTA_DADOS / "serpapi_uso.json"


def link_google_flights(origem_busca, destino_busca, ida, volta):
    q = f"Flights from {origem_busca} to {destino_busca} on {ida} through {volta}"
    return f"https://www.google.com/travel/flights?q={quote(q)}&curr=BRL&hl=pt-BR"


def _uso(mes):
    if ARQUIVO_USO.exists():
        return json.loads(ARQUIVO_USO.read_text(encoding="utf-8")).get(mes, 0)
    return 0


def _registrar_uso(mes, n):
    atual = json.loads(ARQUIVO_USO.read_text(encoding="utf-8")) if ARQUIVO_USO.exists() else {}
    atual[mes] = atual.get(mes, 0) + n
    ARQUIVO_USO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_USO.write_text(json.dumps(atual, indent=1, sort_keys=True), encoding="utf-8")


def veredito(preco_achado, resultado, tolerancia):
    menor = resultado.get("menor_preco")
    if not menor:
        return "sem_resposta"
    if menor > preco_achado * (1 + tolerancia):
        return "preco_mudou"
    faixa = resultado.get("faixa_tipica")
    baixo = resultado.get("nivel") == "low" or (faixa and menor < faixa[0])
    return "confirmado" if baixo else "nao_confirmado"


def conferir_pendentes(estado, config, indice, chave, agora, log=print):
    """Confere os achados ainda não conferidos, priorizando São Paulo e os maiores descontos."""
    if not chave:
        return 0
    regras = config["conferencia"]
    mes = agora.strftime("%Y-%m")
    restante_mes = regras["teto_mensal"] - _uso(mes)
    limite = min(regras["max_por_execucao"], max(0, restante_mes))
    if limite <= 0:
        log("Conferência: teto mensal da SerpApi atingido, nada conferido nesta execução.")
        return 0

    pendentes = [a for a in estado["ativos"].values()
                 if not a.get("conferencia") and not (a.get("curadoria") or {}).get("status") == "descartado"]
    pendentes.sort(key=lambda a: (indice[a["rota"].split("-")[0]].get("prioridade", 1), -a["desconto"]))

    feitas = 0
    for a in pendentes[:limite]:
        orig_cod, dest_cod = a["rota"].split("-")
        orig = a.get("aeroporto_origem") or indice[orig_cod]["aeroportos"]
        dest = a.get("aeroporto_destino") or indice[dest_cod]["aeroportos"]
        try:
            res = serpapi.conferir(orig, dest, a["ida"], a["volta"], chave)
        except ErroFonte as e:
            log(f"Conferência falhou para {a['id']}: {e}")
            if e.definitivo:
                break
            continue
        feitas += 1
        a["conferencia"] = {
            "veredito": veredito(a["preco"], res, regras["tolerancia_preco"]),
            "preco_google": res.get("menor_preco"),
            "nivel_google": res.get("nivel"),
            "faixa_tipica": res.get("faixa_tipica"),
            "em": agora.isoformat(),
        }
        log(f"Conferido {a['id']}: {a['conferencia']['veredito']} (Google R$ {res.get('menor_preco')})")
    if feitas:
        _registrar_uso(mes, feitas)
    return feitas
