"""Histórico enxuto: um resumo por rota por dia (quantos preços, mediana, quartil, mínimo).

Fica em data/historico/AAAA-MM-DD.json. É pequeno de propósito, para caber no repositório.
Com o tempo, o "preço normal" passa a usar a mediana dos últimos 30 dias, não só a varredura do dia.
"""

import json
import statistics
from datetime import date, timedelta

from .config import PASTA_DADOS

PASTA = PASTA_DADOS / "historico"


def resumir(precos):
    precos = sorted(precos)
    if not precos:
        return None
    n = len(precos)
    return {
        "n": n,
        "mediana": round(statistics.median(precos), 2),
        "p25": round(precos[max(0, int(n * 0.25) - 1)], 2) if n >= 4 else round(precos[0], 2),
        "minimo": round(precos[0], 2),
    }


def salvar_resumo_do_dia(dia_iso, resumos, quando_iso):
    """resumos: {chave_rota: resumo}. Junta com o que já existe para o dia."""
    PASTA.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA / f"{dia_iso}.json"
    atual = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    for chave, resumo in resumos.items():
        if resumo:
            atual[chave] = {**resumo, "atualizado": quando_iso}
    arquivo.write_text(json.dumps(atual, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def medianas_recentes(chave, dias=30, hoje=None, excluir_hoje=True):
    """Medianas diárias da rota nos últimos `dias` (sem contar hoje, que vem da varredura atual)."""
    hoje = hoje or date.today()
    saida = []
    inicio = 1 if excluir_hoje else 0
    for k in range(inicio, dias + 1):
        arquivo = PASTA / f"{(hoje - timedelta(days=k)).isoformat()}.json"
        if not arquivo.exists():
            continue
        try:
            dado = json.loads(arquivo.read_text(encoding="utf-8")).get(chave)
        except (json.JSONDecodeError, OSError):
            continue
        if dado and dado.get("mediana"):
            saida.append(dado["mediana"])
    return saida
