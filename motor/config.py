"""Configuração: caminhos, variáveis de ambiente (.env) e a lista de rotas."""

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
PASTA_SITE = RAIZ / "docs"
ARQUIVO_CONFIG = RAIZ / "config" / "rotas.json"


def carregar_env(caminho=None):
    """Lê o .env (KEY=valor) sem sobrescrever variáveis já definidas no ambiente."""
    caminho = Path(caminho) if caminho else RAIZ / ".env"
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


def carregar_config(caminho=None):
    caminho = Path(caminho) if caminho else ARQUIVO_CONFIG
    return json.loads(caminho.read_text(encoding="utf-8"))


def token_travelpayouts():
    return os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()


def chave_serpapi():
    return os.environ.get("SERPAPI_KEY", "").strip()


def agora_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def meses_da_busca(config, hoje=None):
    """Lista 'AAAA-MM' dos meses de saída pesquisados (ex.: de 1 a 9 meses à frente)."""
    hoje = hoje or date.today()
    busca = config["busca"]
    meses = []
    for k in range(busca["meses_a_frente_de"], busca["meses_a_frente_ate"] + 1):
        ano = hoje.year + (hoje.month - 1 + k) // 12
        mes = (hoje.month - 1 + k) % 12 + 1
        meses.append(f"{ano:04d}-{mes:02d}")
    return meses


def rotas(config, agenda="todas", hora_utc=None, origens=None):
    """Gera as rotas a pesquisar nesta execução.

    agenda="todas": todas as rotas.
    agenda="auto": prioridade 1 sempre; prioridade 2 só nas horas UTC definidas em config["agenda"].
    origens: lista de códigos para limitar (ex.: ["SAO"]).
    """
    if hora_utc is None:
        hora_utc = agora_utc().hour
    horas_p2 = set(config.get("agenda", {}).get("horas_utc_prioridade_2", [0, 12]))
    for orig in config["origens"]:
        if origens and orig["codigo"] not in origens:
            continue
        if agenda == "auto" and orig.get("prioridade", 1) > 1 and hora_utc not in horas_p2:
            continue
        for dest in config["destinos"]:
            yield {
                "chave": f"{orig['codigo']}-{dest['codigo']}",
                "origem": orig,
                "destino": dest,
                "prioridade": orig.get("prioridade", 1),
            }


def indice_cidades(config):
    """Mapa código -> dados da cidade (origens e destinos)."""
    indice = {}
    for item in config["origens"] + config["destinos"]:
        indice[item["codigo"]] = item
    return indice
