"""Estado dos achados entre execuções: data/achados.json.

Cada achado tem: quando apareceu, quando foi visto pela última vez, conferência no Google
e a sua curadoria (conferido / descartado). Achados que somem da fonte por mais de
`validade_horas` vão para "expirados" e continuam contando no relatório final.
"""

import json
from datetime import datetime, timedelta

from .config import PASTA_DADOS
from .deteccao import id_achado

ARQUIVO = PASTA_DADOS / "achados.json"
ARQUIVO_ROTAS = PASTA_DADOS / "rotas_status.json"


def carregar(arquivo=None):
    arquivo = arquivo or ARQUIVO
    if arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))
    return {"ativos": {}, "expirados": {}}


def salvar(estado, arquivo=None):
    arquivo = arquivo or ARQUIVO
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def _dt(iso):
    return datetime.fromisoformat(iso)


def mesclar(estado, novos, rotas_varridas, agora, validade_horas):
    """Atualiza o estado com os achados desta execução.

    Só expira achados das rotas que foram varridas agora (uma rota de prioridade 2 que ficou
    de fora desta execução mantém os achados dela).
    """
    agora_iso = agora.isoformat()
    vistos = set()
    for a in novos:
        ident = id_achado(a)
        vistos.add(ident)
        anterior = estado["ativos"].get(ident) or estado["expirados"].pop(ident, None)
        if anterior:
            registro = {**anterior, **a, "id": ident, "visto_em": agora_iso}
            registro["primeiro_em"] = anterior.get("primeiro_em", agora_iso)
            registro["menor_preco_visto"] = min(anterior.get("menor_preco_visto", a["preco"]), a["preco"])
            # Se o preço subiu muito, a conferência antiga deixa de valer.
            conf = anterior.get("conferencia")
            if conf and a["preco"] > anterior.get("preco", a["preco"]) * 1.10:
                registro["conferencia"] = None
        else:
            registro = {**a, "id": ident, "primeiro_em": agora_iso, "visto_em": agora_iso,
                        "menor_preco_visto": a["preco"], "conferencia": None, "curadoria": None}
        estado["ativos"][ident] = registro

    limite = agora - timedelta(hours=validade_horas)
    for ident in list(estado["ativos"]):
        a = estado["ativos"][ident]
        if ident in vistos or a["rota"] not in rotas_varridas:
            continue
        if _dt(a["visto_em"]) < limite:
            estado["expirados"][ident] = {**a, "expirado_em": agora_iso}
            del estado["ativos"][ident]
    return estado


def marcar(estado, ident, status, nota=None, agora=None):
    """Curadoria manual: status 'conferido' ou 'descartado' (ou None para limpar)."""
    alvo = estado["ativos"].get(ident) or estado["expirados"].get(ident)
    if not alvo:
        raise KeyError(ident)
    alvo["curadoria"] = None if status is None else {
        "status": status,
        "nota": nota or "",
        "em": (agora.isoformat() if agora else None),
    }
    return alvo


def salvar_status_rotas(status_rotas, agora, arquivo=None):
    """Junta o status desta execução com o das rotas que não foram varridas agora."""
    arquivo = arquivo or ARQUIVO_ROTAS
    atual = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
    for chave, s in status_rotas.items():
        atual[chave] = {**s, "varrida_em": agora.isoformat()}
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(atual, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return atual


def carregar_status_rotas(arquivo=None):
    arquivo = arquivo or ARQUIVO_ROTAS
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
