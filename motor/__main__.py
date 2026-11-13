"""Linha de comando do motor.

    python3 -m motor diagnostico            # testa o token e mostra o formato dos dados (1 rota)
    python3 -m motor rodar --todas          # varre todas as rotas, detecta, confere e gera o site
    python3 -m motor rodar --agenda auto    # como no robô agendado: SP sempre, demais 2x por dia
    python3 -m motor cobertura              # quanto cada rota rendeu na última varredura
    python3 -m motor marcar ID conferido    # curadoria manual (conferido / descartado / limpar)
    python3 -m motor relatorio              # resumo do teste para a conversa final
    python3 -m motor exemplo                # prévia do site com dados fictícios (não vai para docs/)
"""

import argparse
import json
import sys
import time
from datetime import date, timedelta

from . import conferencia, deteccao, estado as est, historico, observacoes, site
from .config import (PASTA_DADOS, agora_utc, carregar_config, carregar_env, chave_serpapi, indice_cidades,
                     meses_da_busca, rotas, token_travelpayouts)
from .fontes import ErroFonte, get_json
from .fontes import travelpayouts


def _brl(v):
    return "–" if v is None else f"R$ {v:,.0f}".replace(",", ".")


def cmd_rodar(args):
    config = carregar_config()
    indice = indice_cidades(config)
    token = token_travelpayouts()
    if not token:
        print("Falta o TRAVELPAYOUTS_TOKEN no .env (ou nos segredos do GitHub). Veja o README.", file=sys.stderr)
        return 2
    agora = agora_utc()
    agenda = "todas" if args.todas else args.agenda
    origens = [o.strip().upper() for o in args.origem.split(",")] if args.origem else None
    lista = list(rotas(config, agenda=agenda, hora_utc=agora.hour, origens=origens))
    meses = meses_da_busca(config)
    busca, regras = config["busca"], config["regras"]
    print(f"Varrendo {len(lista)} rotas × {len(meses)} meses ({meses[0]} a {meses[-1]})...")

    novos, status_rotas, resumos_hist = [], {}, {}
    for r in lista:
        chave = r["chave"]
        bilhetes, erros = [], []
        # Primeiro a consulta sem mês (traz ~90 pares de datas), depois um reforço por mês.
        for mes in [None] + meses:
            try:
                bilhetes += travelpayouts.buscar_mes(r["origem"]["codigo"], r["destino"]["codigo"], mes, token,
                                                     moeda=config["moeda"], mercado=config.get("mercado"),
                                                     limite=busca["limite_por_consulta"])
            except ErroFonte as e:
                if e.definitivo:
                    print(f"Parando: {e}", file=sys.stderr)
                    return 2
                erros.append(f"{mes or 'próximas'}: {e}")
            time.sleep(busca["pausa_entre_consultas_s"])
        dias = regras["dias_historico"]
        medianas = historico.medianas_recentes(chave, dias)
        medianas_mes = {m: historico.medianas_recentes(deteccao.chave_mes(chave, m), dias) for m in meses}
        atuais = deteccao.validos(bilhetes, busca)
        memoria = observacoes.atualizar(chave, atuais, agora, regras.get("dias_memoria", 10))
        guardados = observacoes.como_bilhetes(memoria, excluir={f"{b['ida']}|{b['volta']}" for b in atuais})
        resumo, achados = deteccao.detectar(chave, bilhetes + guardados, regras, busca, medianas, medianas_mes)
        resumo["da_memoria"] = len(guardados)
        if erros and not bilhetes:
            resumo["status"] = "erro"
        resumo["erros"] = len(erros)
        status_rotas[chave] = resumo
        for k, precos in deteccao.resumos_para_historico(chave, deteccao.validos(bilhetes, busca)).items():
            resumos_hist[k] = historico.resumir(precos)
        novos += achados
        print(f"  {chave:<8} {resumo['amostra']:>4} datas  normal {_brl(resumo.get('preco_normal')):>10}  "
              f"achados {len(achados)}{'  (erros: %d)' % len(erros) if erros else ''}")

    historico.salvar_resumo_do_dia(agora.date().isoformat(), resumos_hist, agora.isoformat())
    estado = est.carregar()
    antes = set(estado["ativos"])
    est.mesclar(estado, novos, {r["chave"] for r in lista}, agora, regras["validade_horas"])
    if not args.sem_conferencia:
        conferencia.conferir_pendentes(estado, config, indice, chave_serpapi(), agora)
    est.salvar(estado)
    todas_rotas = est.salvar_status_rotas(status_rotas, agora)
    destino = site.gerar(estado, todas_rotas, config, indice, agora)

    novos_ids = set(estado["ativos"]) - antes
    com_dados = sum(1 for s in status_rotas.values() if s["status"] == "ok")
    print(f"\nRotas com dados: {com_dados} de {len(status_rotas)}. Achados ativos: {len(estado['ativos'])} "
          f"({len(novos_ids)} novos). Site: {destino}")
    return 0


def cmd_diagnostico(args):
    token = token_travelpayouts()
    if not token:
        print("Falta o TRAVELPAYOUTS_TOKEN no .env. Veja o README.", file=sys.stderr)
        return 2
    config = carregar_config()
    origem, destino = args.rota.upper().split("-")
    mes = args.mes or meses_da_busca(config)[0]
    for mercado in (None, "br"):
        params = {"origin": origem, "destination": destino, "departure_at": mes, "one_way": "false",
                  "sorting": "price", "unique": "false", "currency": "brl", "limit": 1000, "market": mercado,
                  "token": token}
        rotulo = f"mercado={mercado or 'padrão'}"
        try:
            dados = get_json(travelpayouts.API, params)
        except ErroFonte as e:
            print(f"[{rotulo}] erro: {e}")
            if e.definitivo:
                return 2
            continue
        itens = dados.get("data") or []
        print(f"[{rotulo}] success={dados.get('success')} moeda={dados.get('currency')} itens={len(itens)}")
        if itens:
            print("  campos do primeiro item:", ", ".join(sorted(itens[0].keys())))
            print("  primeiro item:", json.dumps(itens[0], ensure_ascii=False))
            datas = {(i.get('departure_at', '')[:10], i.get('return_at', '')[:10]) for i in itens}
            print(f"  pares de datas distintos: {len(datas)}")
    print("\nSe o mercado 'br' trouxer bem mais itens, mude \"mercado\" para \"br\" em config/rotas.json.")
    return 0


def cmd_cobertura(args):
    status = est.carregar_status_rotas()
    if not status:
        print("Ainda não houve varredura. Rode: python3 -m motor rodar --todas")
        return 1
    print(f"{'Rota':<9} {'Situação':<14} {'Datas':>6} {'Normal':>11} {'Menor':>11} {'Achados':>8}")
    for chave in sorted(status):
        s = status[chave]
        print(f"{chave:<9} {s.get('status',''):<14} {s.get('amostra',0):>6} {_brl(s.get('preco_normal')):>11} "
              f"{_brl(s.get('menor_preco')):>11} {s.get('achados',0):>8}")
    ok = sum(1 for s in status.values() if s.get("status") == "ok")
    print(f"\n{ok} de {len(status)} rotas com dados suficientes.")
    return 0


def cmd_marcar(args):
    config = carregar_config()
    estado = est.carregar()
    status = None if args.status == "limpar" else args.status
    try:
        alvo = est.marcar(estado, args.id, status, args.nota, agora_utc())
    except KeyError:
        print(f"Achado não encontrado: {args.id}. Os IDs estão em data/achados.json.", file=sys.stderr)
        return 1
    est.salvar(estado)
    site.gerar(estado, est.carregar_status_rotas(), config, indice_cidades(config), agora_utc())
    print(f"{alvo['id']}: {args.status}. Site atualizado.")
    return 0


def cmd_site(args):
    config = carregar_config()
    destino = site.gerar(est.carregar(), est.carregar_status_rotas(), config, indice_cidades(config), agora_utc())
    print(f"Site gerado: {destino}")
    return 0


def _conferido(a):
    return (a.get("curadoria") or {}).get("status") == "conferido" or (a.get("conferencia") or {}).get("veredito") == "confirmado"


def cmd_relatorio(args):
    config = carregar_config()
    indice = indice_cidades(config)
    estado = est.carregar()
    todos = [a for a in list(estado["ativos"].values()) + list(estado["expirados"].values())
             if (a.get("curadoria") or {}).get("status") != "descartado"]
    if not todos:
        print("Nenhum achado registrado ainda.")
        return 1
    nome = lambda cod: indice.get(cod, {}).get("nome", cod)
    conferidos = [a for a in todos if _conferido(a)]
    mudou = [a for a in todos if (a.get("conferencia") or {}).get("veredito") == "preco_mudou"]
    media = sum(a["desconto"] for a in todos) / len(todos)
    linhas = ["# Relatório do teste do motor", "",
              f"- Achados no período: **{len(todos)}** (ativos agora: {len(estado['ativos'])})",
              f"- Conferidos (Google ou manual): **{len(conferidos)}**; preço já tinha mudado na conferência: {len(mudou)}",
              f"- Desconto médio sobre o preço normal da rota: **{media:.0%}**",
              f"- Possíveis erros tarifários: {sum(1 for a in todos if a.get('erro_tarifario'))}", "",
              "## Melhores achados", "", "| Rota | Datas | Preço | Normal | Desconto | Conferido |", "|---|---|---|---|---|---|"]
    for a in sorted(todos, key=lambda a: -a["desconto"])[:10]:
        o, d = a["rota"].split("-")
        linhas.append(f"| {nome(o)} → {nome(d)} | {a['ida']} a {a['volta']} | {_brl(a['preco'])} | "
                      f"{_brl(a['preco_normal'])} | {a['desconto']:.0%} | {'sim' if _conferido(a) else 'não'} |")
    por_dest = {}
    for a in todos:
        por_dest[a["rota"].split("-")[1]] = por_dest.get(a["rota"].split("-")[1], 0) + 1
    linhas += ["", "## Achados por destino", ""]
    linhas += [f"- {nome(k)}: {v}" for k, v in sorted(por_dest.items(), key=lambda kv: -kv[1])]
    status = est.carregar_status_rotas()
    sem = [k for k, s in status.items() if s.get("status") != "ok"]
    if sem:
        linhas += ["", "## Rotas com poucos dados na última varredura", "", ", ".join(sorted(sem))]
    texto = "\n".join(linhas) + "\n"
    (PASTA_DADOS / "relatorio.md").write_text(texto, encoding="utf-8")
    print(texto)
    print(f"Salvo em {PASTA_DADOS / 'relatorio.md'}")
    return 0


def cmd_exemplo(args):
    """Prévia visual com dados fictícios, salva fora do site publicado."""
    config = carregar_config()
    indice = indice_cidades(config)
    agora = agora_utc()
    hoje = date.today()
    exemplos = [("SAO", "LIS", 45, 14, 2890, 4700, "TP", True), ("SAO", "SHA", 80, 18, 4390, 6900, "ET", False),
                ("RIO", "PAR", 120, 10, 2650, 4400, "AF", True), ("SAO", "MIA", 60, 7, 1490, 3300, "AA", False)]
    estado = {"ativos": {}, "expirados": {}}
    for o, d, em, est_dias, preco, normal, cia, conf in exemplos:
        ida = (hoje + timedelta(days=em)).isoformat()
        volta = (hoje + timedelta(days=em + est_dias)).isoformat()
        ident = f"{o}-{d}-{ida}-{volta}"
        estado["ativos"][ident] = {
            "id": ident, "rota": f"{o}-{d}", "ida": ida, "volta": volta, "estadia_dias": est_dias, "preco": preco,
            "preco_normal": normal, "desconto": round(1 - preco / normal, 4), "erro_tarifario": 1 - preco / normal >= 0.5,
            "cia": cia, "escalas_ida": 1, "escalas_volta": 1, "visto_em": agora.isoformat(), "primeiro_em": agora.isoformat(),
            "conferencia": {"veredito": "confirmado", "em": agora.isoformat(), "preco_google": preco} if conf else None,
            "curadoria": None, "link_aviasales": "",
        }
    status = {"SAO-LIS": {"status": "ok", "amostra": 84, "preco_normal": 4700, "menor_preco": 2890, "achados": 1,
                          "varrida_em": agora.isoformat()}}
    destino = site.gerar(estado, status, config, indice, agora, destino=PASTA_DADOS / "previa_exemplo.html",
                         aviso_exemplo=True)
    print(f"Prévia com dados fictícios: {destino}")
    return 0


def main(argv=None):
    carregar_env()
    p = argparse.ArgumentParser(prog="python3 -m motor", description="Motor de achados do Clube VIP")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rodar", help="varre as rotas, detecta, confere e gera o site")
    r.add_argument("--todas", action="store_true", help="todas as rotas, ignorando a agenda")
    r.add_argument("--agenda", default="auto", choices=["auto", "todas"])
    r.add_argument("--origem", help="só estas origens, ex.: SAO ou SAO,RIO")
    r.add_argument("--sem-conferencia", action="store_true", help="não usa a SerpApi nesta execução")
    r.set_defaults(fn=cmd_rodar)
    d = sub.add_parser("diagnostico", help="testa o token e mostra o formato dos dados")
    d.add_argument("--rota", default="SAO-LIS")
    d.add_argument("--mes", help="AAAA-MM (padrão: próximo mês)")
    d.set_defaults(fn=cmd_diagnostico)
    sub.add_parser("cobertura", help="quanto cada rota rendeu na última varredura").set_defaults(fn=cmd_cobertura)
    m = sub.add_parser("marcar", help="curadoria manual de um achado")
    m.add_argument("id")
    m.add_argument("status", choices=["conferido", "descartado", "limpar"])
    m.add_argument("--nota")
    m.set_defaults(fn=cmd_marcar)
    sub.add_parser("site", help="só gera o site de novo").set_defaults(fn=cmd_site)
    sub.add_parser("relatorio", help="resumo do teste").set_defaults(fn=cmd_relatorio)
    sub.add_parser("exemplo", help="prévia do site com dados fictícios").set_defaults(fn=cmd_exemplo)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
