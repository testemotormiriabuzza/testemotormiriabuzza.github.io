"""Fontes de preço do motor."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "motor-clube-vip/0.1"


class ErroFonte(Exception):
    """Falha ao consultar uma fonte de preços. `definitivo` indica que repetir não adianta."""

    def __init__(self, mensagem, definitivo=False):
        super().__init__(mensagem)
        self.definitivo = definitivo


def get_json(url, params, tentativas=3, timeout=30, cabecalhos=None):
    """GET com novas tentativas para erros temporários (429 e 5xx)."""
    consulta = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    pedido = urllib.request.Request(
        f"{url}?{consulta}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT, **(cabecalhos or {})},
    )
    ultimo_erro = None
    for tentativa in range(tentativas):
        try:
            with urllib.request.urlopen(pedido, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            corpo = ""
            try:
                corpo = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if e.code in (401, 403):
                raise ErroFonte(f"acesso negado ({e.code}). Confira a chave/token. {corpo}", definitivo=True)
            if e.code == 400:
                raise ErroFonte(f"pedido inválido (400): {corpo}", definitivo=True)
            ultimo_erro = ErroFonte(f"HTTP {e.code}: {corpo}")
            if e.code not in (429, 500, 502, 503, 504):
                raise ultimo_erro
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo_erro = ErroFonte(f"falha de rede ou resposta inválida: {e}")
        time.sleep(2 * (tentativa + 1))
    raise ultimo_erro
