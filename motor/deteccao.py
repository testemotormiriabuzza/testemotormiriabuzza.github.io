"""Detecção: compara cada preço com o preço normal e separa os achados.

Preço normal, nesta ordem:
1. do mês de saída na rota (mediana das datas daquele mês), quando houver pelo menos
   `amostra_minima_mes` datas, combinada com o histórico daquele mês;
2. senão, da rota inteira (mediana de todas as datas varridas), combinada com o histórico da rota.
Usar o mês evita confundir baixa temporada com promoção.
Achado = pelo menos `desconto_minimo` abaixo do normal (padrão 30%).
Possível erro tarifário = pelo menos `desconto_erro_tarifario` abaixo (padrão 50%).
"""

import statistics
from datetime import date, timedelta


def dias_entre(ida, volta):
    try:
        return (date.fromisoformat(volta) - date.fromisoformat(ida)).days
    except ValueError:
        return None


def filtrar_estadia(bilhetes, min_dias, max_dias, antecedencia_min_dias=0, hoje=None):
    hoje = hoje or date.today()
    limite = hoje + timedelta(days=antecedencia_min_dias)
    saida = []
    for b in bilhetes:
        d = dias_entre(b["ida"], b["volta"])
        try:
            ida = date.fromisoformat(b["ida"])
        except ValueError:
            continue
        if d is not None and min_dias <= d <= max_dias and ida >= limite:
            saida.append({**b, "estadia_dias": d})
    return saida


def menor_por_datas(bilhetes):
    """Um bilhete por par de datas (ida, volta): o mais barato."""
    melhor = {}
    for b in bilhetes:
        chave = (b["ida"], b["volta"])
        if chave not in melhor or b["preco"] < melhor[chave]["preco"]:
            melhor[chave] = b
    return list(melhor.values())


def validos(bilhetes, busca, hoje=None):
    return menor_por_datas(filtrar_estadia(bilhetes, busca["estadia_min_dias"], busca["estadia_max_dias"],
                                           busca.get("antecedencia_min_dias", 0), hoje))


def preco_normal(precos_hoje, medianas_hist):
    if not precos_hoje:
        return None
    hoje = statistics.median(precos_hoje)
    if not medianas_hist:
        return round(hoje, 2)
    # Mediana das medianas: o histórico pesa mais conforme os dias se acumulam.
    return round(statistics.median(list(medianas_hist) + [hoje]), 2)


def chave_mes(chave_rota, mes):
    return f"{chave_rota}@{mes}"


def detectar(chave_rota, bilhetes, regras, busca, medianas_hist=(), medianas_mes=None, hoje=None):
    """Devolve (resumo_da_rota, achados).

    medianas_hist: medianas diárias anteriores da rota inteira.
    medianas_mes: {"AAAA-MM": [medianas diárias anteriores daquele mês de saída]}.
    """
    medianas_mes = medianas_mes or {}
    vals = validos(bilhetes, busca, hoje)
    precos = [b["preco"] for b in vals]
    resumo = {"rota": chave_rota, "amostra": len(precos), "dias_historico": len(medianas_hist)}
    if len(precos) < regras["amostra_minima"]:
        resumo.update(status="poucos_dados", preco_normal=None, menor_preco=min(precos) if precos else None)
        return resumo, []

    normal_rota = preco_normal(precos, medianas_hist)
    por_mes = {}
    for b in vals:
        por_mes.setdefault(b["ida"][:7], []).append(b["preco"])
    min_mes = regras.get("amostra_minima_mes", 6)
    normais_mes = {m: preco_normal(ps, medianas_mes.get(m, ())) for m, ps in por_mes.items() if len(ps) >= min_mes}
    resumo.update(status="ok", preco_normal=normal_rota, menor_preco=min(precos), meses_com_base=len(normais_mes))

    max_escalas = regras.get("max_escalas")
    candidatos = []
    for b in vals:
        if b.get("memoria"):
            continue  # preço guardado de varreduras anteriores: só entra no preço normal
        if max_escalas is not None and any((b.get(k) or 0) > max_escalas for k in ("escalas_ida", "escalas_volta")):
            continue
        mes = b["ida"][:7]
        normal, base = (normais_mes[mes], "mes") if mes in normais_mes else (normal_rota, "rota")
        if b["preco"] <= normal * (1 - regras["desconto_minimo"]):
            desconto = 1 - b["preco"] / normal
            candidatos.append({
                **b,
                "rota": chave_rota,
                "preco_normal": normal,
                "base_normal": base,
                "desconto": round(desconto, 4),
                "erro_tarifario": desconto >= regras["desconto_erro_tarifario"],
            })

    # Um achado por mês de saída (o melhor), depois os melhores da rota.
    melhor_mes = {}
    for c in sorted(candidatos, key=lambda c: (-c["desconto"], c["preco"])):
        melhor_mes.setdefault(c["ida"][:7], c)
    escolhidos = sorted(melhor_mes.values(), key=lambda c: (-c["desconto"], c["preco"]))[: regras["max_achados_por_rota"]]
    resumo["candidatos"] = len(candidatos)
    resumo["achados"] = len(escolhidos)
    return resumo, escolhidos


def resumos_para_historico(chave_rota, vals):
    """Precos agrupados para o histórico: rota inteira e cada mês de saída."""
    grupos = {chave_rota: [b["preco"] for b in vals]}
    for b in vals:
        grupos.setdefault(chave_mes(chave_rota, b["ida"][:7]), []).append(b["preco"])
    return grupos


def id_achado(a):
    return f"{a['rota']}-{a['ida']}-{a['volta']}"
