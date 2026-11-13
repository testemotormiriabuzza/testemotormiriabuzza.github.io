"""Gera o site do teste (docs/index.html): uma página só, com os dados embutidos e filtros em JS."""

import json
from pathlib import Path

from .conferencia import link_google_flights
from .config import PASTA_SITE

CIAS = {
    "TP": "TAP", "LA": "LATAM", "JJ": "LATAM", "AF": "Air France", "KL": "KLM", "IB": "Iberia",
    "UX": "Air Europa", "LH": "Lufthansa", "LX": "Swiss", "OS": "Austrian", "TK": "Turkish Airlines",
    "AA": "American", "UA": "United", "DL": "Delta", "AC": "Air Canada", "EK": "Emirates",
    "QR": "Qatar Airways", "EY": "Etihad", "ET": "Ethiopian", "CA": "Air China", "MU": "China Eastern",
    "CZ": "China Southern", "CX": "Cathay Pacific", "NH": "ANA", "JL": "Japan Airlines", "KE": "Korean Air",
    "SQ": "Singapore Airlines", "AD": "Azul", "G3": "Gol", "CM": "Copa", "AV": "Avianca", "BA": "British Airways",
    "AZ": "ITA Airways", "AT": "Royal Air Maroc", "MS": "EgyptAir", "AR": "Aerolíneas Argentinas",
    "H2": "Sky Airline", "AM": "Aeroméxico", "SK": "SAS", "LO": "LOT", "TS": "Air Transat", "WS": "WestJet",
}


def status_exibicao(a):
    cur = (a.get("curadoria") or {}).get("status")
    if cur == "descartado":
        return None
    if cur == "conferido":
        return "conferido"
    conf = a.get("conferencia") or {}
    v = conf.get("veredito")
    if v == "confirmado":
        return "conferido"
    if v == "preco_mudou":
        return None
    return "a_conferir"


def montar_dados(estado, status_rotas, config, indice, gerado_em):
    achados = []
    for a in estado["ativos"].values():
        st = status_exibicao(a)
        if not st:
            continue
        if st == "a_conferir" and not config["site"].get("mostrar_nao_conferidos", True):
            continue
        orig_cod, dest_cod = a["rota"].split("-")
        orig, dest = indice.get(orig_cod, {}), indice.get(dest_cod, {})
        conf = a.get("conferencia") or {}
        achados.append({
            "id": a["id"],
            "origem": orig_cod,
            "destino": dest_cod,
            "origem_nome": orig.get("nome", orig_cod),
            "origem_detalhe": a.get("aeroporto_origem") or orig.get("detalhe", ""),
            "destino_nome": dest.get("nome", dest_cod),
            "destino_detalhe": a.get("aeroporto_destino") or "",
            "ida": a["ida"],
            "volta": a["volta"],
            "estadia_dias": a.get("estadia_dias"),
            "preco": a["preco"],
            "preco_normal": a["preco_normal"],
            "desconto": a["desconto"],
            "erro_tarifario": a.get("erro_tarifario", False),
            "cia": CIAS.get(a.get("cia", ""), a.get("cia", "")),
            "vendedor": a.get("vendedor") or "",
            "base_normal": a.get("base_normal") or "rota",
            "escalas_ida": a.get("escalas_ida"),
            "escalas_volta": a.get("escalas_volta"),
            "visto_em": a["visto_em"],
            "primeiro_em": a["primeiro_em"],
            "status": st,
            "conferido_por": "google" if conf.get("veredito") == "confirmado" else ("manual" if st == "conferido" else ""),
            "conferido_em": conf.get("em") or (a.get("curadoria") or {}).get("em"),
            "preco_google": conf.get("preco_google"),
            "nota_conferencia": "O preço bate, mas o Google não marca como baixo." if conf.get("veredito") == "nao_confirmado" else "",
            "link_google": link_google_flights(orig.get("busca", orig_cod), dest.get("busca", dest_cod), a["ida"], a["volta"]),
            "link_aviasales": a.get("link_aviasales") or "",
        })

    rotas = []
    for orig in config["origens"]:
        for dest in config["destinos"]:
            chave = f"{orig['codigo']}-{dest['codigo']}"
            s = status_rotas.get(chave, {})
            rotas.append({
                "chave": chave,
                "origem_nome": orig["nome"],
                "destino_nome": dest["nome"],
                "status": s.get("status", "nao_varrida"),
                "amostra": s.get("amostra", 0),
                "preco_normal": s.get("preco_normal"),
                "menor_preco": s.get("menor_preco"),
                "achados": s.get("achados", 0),
                "varrida_em": s.get("varrida_em"),
            })

    return {
        "gerado_em": gerado_em.isoformat(),
        "titulo": config["site"]["titulo"],
        "subtitulo": config["site"]["subtitulo"],
        "achados": achados,
        "rotas": rotas,
        "origens": [{"codigo": o["codigo"], "nome": o["nome"]} for o in config["origens"]],
        "destinos": [{"codigo": d["codigo"], "nome": d["nome"]} for d in config["destinos"]],
    }


def gerar(estado, status_rotas, config, indice, gerado_em, destino=None, aviso_exemplo=False):
    dados = montar_dados(estado, status_rotas, config, indice, gerado_em)
    if aviso_exemplo:
        dados["aviso_exemplo"] = True
    destino = Path(destino) if destino else PASTA_SITE / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    json_seguro = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    html = MODELO.replace("__TITULO__", _esc(dados["titulo"])).replace("__DADOS__", json_seguro)
    destino.write_text(html, encoding="utf-8")
    return destino


def _esc(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>__TITULO__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;700&family=Fraunces:wght@600&display=swap">
<style>
/* Lista de achados em cartões, com filtros no topo e a tabela de rotas monitoradas no fim. Identidade do Clube VIP. */
:root {
  --bg: #FBF8F3; --surface: #FFFDF9; --surface-2: #F1EBE1; --ink: #14213D; --muted: #4E586B; --line: #E3DACB;
  --accent: #A63D15; --accent-strong: #F26B3A; --ok: #1F6B45; --ok-bg: #DCEFE3; --warn: #7A5200; --warn-bg: #F6E8C8;
  --alert: #A32020; --alert-bg: #FBE3E3;
  --font-display: 'Fraunces', Georgia, serif; --font-body: 'DM Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-data: 'DM Mono', ui-monospace, Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #0E1628; --surface: #15203A; --surface-2: #1B2847; --ink: #E8ECF4; --muted: #A7B2C6; --line: #2A3758;
    --accent: #FF9466; --accent-strong: #F26B3A; --ok: #7AD3A4; --ok-bg: #12342A; --warn: #F2C266; --warn-bg: #3A2C0F;
    --alert: #FF8E8E; --alert-bg: #3D1717; color-scheme: dark; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 15px; line-height: 1.5;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 32px 56px; }
.wrap { max-width: 1080px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }
h1, h2, h3, p { margin: 0; }
a { color: var(--accent); }
a:focus-visible, button:focus-visible, select:focus-visible, input:focus-visible, summary:focus-visible { outline: 2px solid var(--accent-strong); outline-offset: 2px; }
.eyebrow { font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); }
header { display: flex; flex-direction: column; gap: 8px; }
h1 { font-family: var(--font-display); font-weight: 600; font-size: clamp(30px, 5vw, 42px); line-height: 1.05; text-wrap: balance; }
.sub { color: var(--muted); }
.updated { font-family: var(--font-data); font-size: 13px; color: var(--muted); }
.banner { background: var(--warn-bg); color: var(--warn); border-radius: 10px; padding: 10px 14px; font-weight: 700; }
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.stat { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; }
.stat b { font-family: var(--font-data); font-weight: 500; font-size: 24px; font-variant-numeric: tabular-nums; }
.stat span { font-size: 13px; color: var(--muted); }
details.how { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; }
details.how summary { cursor: pointer; font-weight: 700; }
details.how ul { margin: 10px 0 0; padding-left: 20px; display: flex; flex-direction: column; gap: 6px; color: var(--muted); }
.filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; }
.filters label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--muted); font-weight: 500; }
.filters label.check { flex-direction: row; align-items: center; gap: 8px; color: var(--ink); padding-bottom: 8px; }
select { font: inherit; color: var(--ink); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; min-width: 150px; }
input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--accent-strong); }
.count { font-size: 14px; color: var(--muted); margin-left: auto; padding-bottom: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.card .top { display: flex; justify-content: space-between; align-items: start; gap: 8px; }
.route { font-family: var(--font-display); font-weight: 600; font-size: 21px; line-height: 1.15; overflow-wrap: anywhere; }
.airports { font-size: 12px; color: var(--muted); font-family: var(--font-data); }
.chip { font-size: 12px; font-weight: 700; padding: 3px 9px; border-radius: 999px; white-space: nowrap; }
.chip.ok { color: var(--ok); background: var(--ok-bg); }
.chip.pend { color: var(--warn); background: var(--warn-bg); }
.chip.err { color: var(--alert); background: var(--alert-bg); }
.price { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.price b { font-family: var(--font-data); font-weight: 500; font-size: 26px; font-variant-numeric: tabular-nums; }
.off { font-weight: 700; color: var(--accent); }
.normal { font-size: 13px; color: var(--muted); }
.dates { font-size: 14px; }
.meta { font-size: 13px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 4px 12px; }
.links { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 2px; }
.btn { text-decoration: none; font-weight: 700; font-size: 14px; border-radius: 8px; padding: 8px 12px; border: 1px solid var(--line); color: var(--ink); background: var(--surface-2); }
.btn.primary { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.empty { background: var(--surface); border: 1px dashed var(--line); border-radius: 14px; padding: 28px; text-align: center; color: var(--muted); }
section.routes { display: flex; flex-direction: column; gap: 10px; }
section.routes h2 { font-family: var(--font-display); font-weight: 600; font-size: 24px; }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); }
table { width: 100%; border-collapse: collapse; min-width: 620px; font-size: 14px; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); background: var(--surface-2); }
td.num { font-family: var(--font-data); font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: 0; }
footer { font-size: 13px; color: var(--muted); border-top: 1px solid var(--line); padding-top: 14px; }
@media (max-width: 720px) { .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } .count { margin-left: 0; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <span class="eyebrow">Clube VIP · motor de achados</span>
    <h1 id="titulo"></h1>
    <p class="sub" id="subtitulo"></p>
    <p class="updated" id="atualizado"></p>
  </header>
  <p class="banner" id="aviso" hidden>Página de exemplo com dados fictícios, só para ver o visual.</p>
  <div class="stats" id="stats" aria-label="Resumo"></div>
  <details class="how">
    <summary>Como ler os achados</summary>
    <ul>
      <li>Preços de ida e volta por pessoa, em reais, vindos de buscas recentes de outros viajantes.</li>
      <li>"Abaixo do normal" compara com o preço normal da rota naquele mês de saída (ou da rota inteira, quando o mês tem poucas datas), somando os últimos dias conforme o histórico cresce. Assim, baixa temporada não aparece como promoção.</li>
      <li><b>Conferido</b>: o preço foi checado no Google Flights e o Google também considera baixo. <b>A conferir</b>: ainda não foi checado; clique em "Ver no Google Flights" para ver o preço de agora.</li>
      <li>Promoção acaba rápido. Um achado pode sumir horas depois de aparecer.</li>
    </ul>
  </details>
  <div class="filters">
    <label for="f-origem">Origem<select id="f-origem"></select></label>
    <label for="f-destino">Destino<select id="f-destino"></select></label>
    <label for="f-ordem">Ordenar<select id="f-ordem">
      <option value="desconto">Maior desconto</option>
      <option value="preco">Menor preço</option>
      <option value="recente">Mais recentes</option>
      <option value="ida">Data de ida</option>
    </select></label>
    <label class="check" for="f-conferidos"><input type="checkbox" id="f-conferidos"> Só conferidos</label>
    <span class="count" id="contagem" aria-live="polite"></span>
  </div>
  <div class="grid" id="lista"></div>
  <section class="routes">
    <h2>Rotas monitoradas</h2>
    <p class="sub">Quanto o motor conseguiu analisar em cada rota na última varredura.</p>
    <div class="table-wrap"><table id="rotas"></table></div>
  </section>
  <footer>Preços consultados automaticamente e sujeitos a mudança a qualquer momento. Confira sempre o valor final antes de comprar.</footer>
</div>
<script id="dados" type="application/json">__DADOS__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('dados').textContent);
  var tz = 'America/Sao_Paulo';
  var brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
  var pct = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 });
  var dia = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', timeZone: 'UTC' });
  var semana = new Intl.DateTimeFormat('pt-BR', { weekday: 'short', timeZone: 'UTC' });
  var quando = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: tz });
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function dataCurta(iso) { var d = new Date(iso + 'T12:00:00Z'); return semana.format(d).replace('.', '') + ', ' + dia.format(d).replace('.', ''); }
  function hora(iso) { return iso ? quando.format(new Date(iso)) : ''; }
  function escalas(n) { return n == null ? '' : (n === 0 ? 'direto' : n === 1 ? '1 escala' : n + ' escalas'); }

  document.getElementById('titulo').textContent = D.titulo;
  document.getElementById('subtitulo').textContent = D.subtitulo;
  document.getElementById('atualizado').textContent = 'Atualizado em ' + hora(D.gerado_em) + ' (horário de Brasília)';
  document.getElementById('aviso').hidden = !D.aviso_exemplo;

  var conferidos = D.achados.filter(function (a) { return a.status === 'conferido'; });
  var media = D.achados.length ? D.achados.reduce(function (s, a) { return s + a.desconto; }, 0) / D.achados.length : null;
  var comDados = D.rotas.filter(function (r) { return r.status === 'ok'; }).length;
  [[D.achados.length, 'achados ativos'], [conferidos.length, 'conferidos no Google'],
   [media == null ? '–' : pct.format(media), 'desconto médio'], [comDados + ' de ' + D.rotas.length, 'rotas com dados']]
    .forEach(function (s) { var b = el('div', 'stat'); b.append(el('b', null, String(s[0])), el('span', null, s[1])); document.getElementById('stats').append(b); });

  function preencher(sel, itens, todos) {
    sel.append(new Option(todos, ''));
    itens.forEach(function (i) { sel.append(new Option(i.nome, i.codigo)); });
  }
  var fO = document.getElementById('f-origem'), fD = document.getElementById('f-destino');
  var fOrd = document.getElementById('f-ordem'), fC = document.getElementById('f-conferidos');
  preencher(fO, D.origens, 'Todas'); preencher(fD, D.destinos, 'Todos');

  function card(a) {
    var c = el('article', 'card');
    var top = el('div', 'top');
    var t = el('div');
    t.append(el('h3', 'route', a.origem_nome + ' → ' + a.destino_nome));
    var aer = [a.origem_detalhe, a.destino_detalhe].filter(Boolean).join(' → ');
    if (aer) t.append(el('p', 'airports', aer));
    top.append(t);
    var chip;
    if (a.erro_tarifario) chip = el('span', 'chip err', 'Possível erro tarifário');
    else if (a.status === 'conferido') chip = el('span', 'chip ok', 'Conferido');
    else chip = el('span', 'chip pend', 'A conferir');
    top.append(chip);
    c.append(top);
    var p = el('div', 'price');
    p.append(el('b', null, brl.format(a.preco)), el('span', 'off', pct.format(a.desconto) + ' abaixo do normal'));
    c.append(p);
    var mesNome = new Intl.DateTimeFormat('pt-BR', { month: 'long', timeZone: 'UTC' }).format(new Date(a.ida + 'T12:00:00Z'));
    c.append(el('p', 'normal', (a.base_normal === 'mes' ? 'Normal da rota em ' + mesNome + ': ' : 'Normal da rota: ') + brl.format(a.preco_normal) + ' · ida e volta'));
    c.append(el('p', 'dates', dataCurta(a.ida) + ' → ' + dataCurta(a.volta) + (a.estadia_dias ? ' · ' + a.estadia_dias + ' dias' : '')));
    var meta = el('div', 'meta');
    if (a.cia) meta.append(el('span', null, a.cia));
    if (a.vendedor) meta.append(el('span', null, 'vendido por ' + a.vendedor));
    var esc = [escalas(a.escalas_ida), escalas(a.escalas_volta)].filter(Boolean);
    if (esc.length) meta.append(el('span', null, 'ida ' + esc[0] + (esc[1] ? ' · volta ' + esc[1] : '')));
    meta.append(el('span', null, 'visto em ' + hora(a.visto_em)));
    if (a.status === 'conferido' && a.conferido_em) meta.append(el('span', null, (a.conferido_por === 'google' ? 'conferido no Google em ' : 'conferido em ') + hora(a.conferido_em)));
    c.append(meta);
    if (a.nota_conferencia) c.append(el('p', 'normal', a.nota_conferencia));
    var links = el('div', 'links');
    var g = el('a', 'btn primary', 'Ver no Google Flights'); g.href = a.link_google; g.target = '_blank'; g.rel = 'noopener';
    links.append(g);
    if (a.link_aviasales) { var v = el('a', 'btn', 'Ver na Aviasales'); v.href = a.link_aviasales; v.target = '_blank'; v.rel = 'noopener'; links.append(v); }
    c.append(links);
    return c;
  }

  function render() {
    var lista = D.achados.filter(function (a) {
      return (!fO.value || a.origem === fO.value) && (!fD.value || a.destino === fD.value) && (!fC.checked || a.status === 'conferido');
    });
    var ord = fOrd.value;
    lista.sort(function (x, y) {
      if (ord === 'preco') return x.preco - y.preco;
      if (ord === 'recente') return y.primeiro_em.localeCompare(x.primeiro_em);
      if (ord === 'ida') return x.ida.localeCompare(y.ida);
      return y.desconto - x.desconto;
    });
    var box = document.getElementById('lista');
    box.replaceChildren();
    if (!lista.length) {
      box.append(el('p', 'empty', D.achados.length ? 'Nenhum achado com esses filtros.' : 'Ainda não há achados. O motor varre as rotas a cada 6 horas e os achados aparecem aqui.'));
    } else lista.forEach(function (a) { box.append(card(a)); });
    document.getElementById('contagem').textContent = lista.length + (lista.length === 1 ? ' achado' : ' achados');
  }
  [fO, fD, fOrd, fC].forEach(function (x) { x.addEventListener('change', render); });
  render();

  var nomes = { ok: 'Analisada', poucos_dados: 'Poucos preços', erro: 'Erro na consulta', nao_varrida: 'Ainda não varrida' };
  var tab = document.getElementById('rotas');
  var cab = document.createElement('tr');
  ['Rota', 'Preço normal', 'Menor preço', 'Datas analisadas', 'Achados', 'Situação', 'Varrida em'].forEach(function (h) { cab.append(el('th', null, h)); });
  tab.append(cab);
  D.rotas.forEach(function (r) {
    var tr = document.createElement('tr');
    tr.append(el('td', null, r.origem_nome + ' → ' + r.destino_nome),
      el('td', 'num', r.preco_normal ? brl.format(r.preco_normal) : '–'),
      el('td', 'num', r.menor_preco ? brl.format(r.menor_preco) : '–'),
      el('td', 'num', String(r.amostra || 0)),
      el('td', 'num', String(r.achados || 0)),
      el('td', null, nomes[r.status] || r.status),
      el('td', 'num', r.varrida_em ? hora(r.varrida_em) : '–'));
    tab.append(tr);
  });
})();
</script>
</body>
</html>
"""
