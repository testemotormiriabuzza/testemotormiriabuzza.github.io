"""Memória curta de preços por rota (data/observacoes/ROTA.json).

A fonte só mostra o que foi pesquisado nas últimas ~48 horas. Guardando cada par de datas visto nos
últimos `dias` e somando às varreduras seguintes, rotas com poucos dados ganham amostra com o tempo.
As observações antigas só entram no cálculo do preço normal; achado sempre vem da varredura atual.
"""

import json
from datetime import date, datetime, timedelta

from .config import PASTA_DADOS

PASTA = PASTA_DADOS / "observacoes"


def _arquivo(chave):
    return PASTA / f"{chave}.json"


def carregar(chave):
    arq = _arquivo(chave)
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def atualizar(chave, bilhetes_validos, agora, dias=10, hoje=None):
    """Junta os bilhetes desta varredura à memória, descarta o que ficou velho e devolve a memória."""
    hoje = hoje or date.today()
    obs = carregar(chave)
    agora_iso = agora.isoformat()
    for b in bilhetes_validos:
        obs[f"{b['ida']}|{b['volta']}"] = {"preco": b["preco"], "visto_em": agora_iso}
    limite = agora - timedelta(days=dias)
    obs = {k: v for k, v in obs.items()
           if datetime.fromisoformat(v["visto_em"]) >= limite and date.fromisoformat(k.split("|")[0]) >= hoje}
    PASTA.mkdir(parents=True, exist_ok=True)
    _arquivo(chave).write_text(json.dumps(obs, sort_keys=True, indent=0), encoding="utf-8")
    return obs


def como_bilhetes(obs, excluir=()):
    """Observações guardadas no formato de bilhete, sem os pares de datas que já vieram agora."""
    saida = []
    for k, v in obs.items():
        if k in excluir:
            continue
        ida, volta = k.split("|")
        saida.append({"ida": ida, "volta": volta, "preco": v["preco"], "memoria": True})
    return saida
