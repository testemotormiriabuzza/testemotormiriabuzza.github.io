"""Testes com dados sintéticos (não são preços reais)."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from motor import deteccao, estado as est, site
from motor.conferencia import veredito
from motor.config import carregar_config, indice_cidades, meses_da_busca, rotas
from motor.fontes.travelpayouts import normalizar

REGRAS = {"desconto_minimo": 0.30, "desconto_erro_tarifario": 0.50, "amostra_minima": 12,
          "max_achados_por_rota": 3, "validade_horas": 30, "dias_historico": 30}
BUSCA = {"estadia_min_dias": 5, "estadia_max_dias": 25}


def bilhete(ida, dias, preco):
    from datetime import date
    volta = (date.fromisoformat(ida) + timedelta(days=dias)).isoformat()
    return {"ida": ida, "volta": volta, "preco": float(preco), "cia": "TP", "escalas_ida": 1, "escalas_volta": 1}


class TestDeteccao(unittest.TestCase):
    def setUp(self):
        self.bilhetes = [bilhete(f"2027-01-{d:02d}", 10, 5000 + (d % 5) * 100) for d in range(1, 21)]

    def test_sem_promocao(self):
        resumo, achados = deteccao.detectar("SAO-LIS", self.bilhetes, REGRAS, BUSCA)
        self.assertEqual(resumo["status"], "ok")
        self.assertEqual(achados, [])
        self.assertAlmostEqual(resumo["preco_normal"], 5200, delta=150)

    def test_detecta_promocao_e_erro(self):
        b = self.bilhetes + [bilhete("2027-01-25", 9, 3000), bilhete("2027-02-10", 12, 2200)]
        resumo, achados = deteccao.detectar("SAO-LIS", b, REGRAS, BUSCA)
        self.assertEqual(len(achados), 2)
        self.assertTrue(achados[0]["erro_tarifario"])  # 2200 é mais de 50% abaixo
        self.assertFalse(achados[1]["erro_tarifario"])
        self.assertGreaterEqual(achados[1]["desconto"], 0.30)

    def test_um_por_mes(self):
        b = self.bilhetes + [bilhete("2027-01-25", 9, 3000), bilhete("2027-01-26", 9, 3100)]
        _, achados = deteccao.detectar("SAO-LIS", b, REGRAS, BUSCA)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0]["preco"], 3000)

    def test_estadia_fora_da_faixa_e_ignorada(self):
        b = self.bilhetes + [bilhete("2027-01-25", 2, 1000)]
        _, achados = deteccao.detectar("SAO-LIS", b, REGRAS, BUSCA)
        self.assertEqual(achados, [])

    def test_poucos_dados(self):
        resumo, achados = deteccao.detectar("SAO-LIS", self.bilhetes[:5], REGRAS, BUSCA)
        self.assertEqual(resumo["status"], "poucos_dados")
        self.assertEqual(achados, [])

    def test_historico_puxa_o_normal(self):
        _, achados = deteccao.detectar("SAO-LIS", self.bilhetes + [bilhete("2027-01-25", 9, 3700)], REGRAS, BUSCA)
        self.assertEqual(achados, [])  # 3700 é menos de 30% abaixo de ~5200
        _, achados = deteccao.detectar("SAO-LIS", self.bilhetes + [bilhete("2027-01-25", 9, 3700)], REGRAS, BUSCA,
                                       medianas_mes={"2027-01": [6000, 6100, 5900, 6000]})
        self.assertEqual(len(achados), 1)  # com o histórico do mês mais alto, 3700 vira achado

    def test_baixa_temporada_nao_vira_promocao(self):
        # Dezembro caro, março barato: março sozinho não é promoção, porque o normal é do próprio mês.
        dez = [bilhete(f"2026-12-{d:02d}", 10, 8000 + d * 10) for d in range(1, 13)]
        mar = [bilhete(f"2027-03-{d:02d}", 10, 4000 + d * 10) for d in range(1, 13)]
        _, achados = deteccao.detectar("SAO-LIS", dez + mar, REGRAS, BUSCA)
        self.assertEqual(achados, [])
        _, achados = deteccao.detectar("SAO-LIS", dez + mar + [bilhete("2027-03-20", 10, 2500)], REGRAS, BUSCA)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0]["base_normal"], "mes")

    def test_escalas_e_memoria(self):
        duas = {**bilhete("2027-01-25", 9, 3000), "escalas_ida": 2}
        guardado = {**bilhete("2027-01-26", 9, 3000), "memoria": True}
        _, achados = deteccao.detectar("SAO-LIS", self.bilhetes + [duas, guardado], {**REGRAS, "max_escalas": 1}, BUSCA)
        self.assertEqual(achados, [])  # 2 escalas fica de fora; preço da memória não vira achado

    def test_antecedencia_minima(self):
        from datetime import date
        perto = (date.today() + timedelta(days=2)).isoformat()
        b = self.bilhetes + [bilhete(perto, 9, 1000)]
        _, achados = deteccao.detectar("SAO-LIS", b, REGRAS, {**BUSCA, "antecedencia_min_dias": 7})
        self.assertTrue(all(a["ida"] != perto for a in achados))


class TestEstado(unittest.TestCase):
    def test_mesclar_e_expirar(self):
        t0 = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
        a = {"rota": "SAO-LIS", "ida": "2027-01-25", "volta": "2027-02-03", "preco": 3000.0, "desconto": 0.4,
             "preco_normal": 5000}
        estado = {"ativos": {}, "expirados": {}}
        est.mesclar(estado, [a], {"SAO-LIS"}, t0, 30)
        self.assertEqual(len(estado["ativos"]), 1)
        est.mesclar(estado, [], {"RIO-LIS"}, t0 + timedelta(hours=40), 30)
        self.assertEqual(len(estado["ativos"]), 1)  # rota não varrida: não expira
        est.mesclar(estado, [], {"SAO-LIS"}, t0 + timedelta(hours=40), 30)
        self.assertEqual(len(estado["ativos"]), 0)
        self.assertEqual(len(estado["expirados"]), 1)
        est.mesclar(estado, [{**a, "preco": 2900.0}], {"SAO-LIS"}, t0 + timedelta(hours=41), 30)
        ident = deteccao.id_achado(a)
        self.assertIn(ident, estado["ativos"])
        self.assertEqual(estado["ativos"][ident]["menor_preco_visto"], 2900.0)


class TestFontes(unittest.TestCase):
    def test_normalizar_travelpayouts(self):
        t = {"origin": "SAO", "destination": "LIS", "origin_airport": "GRU", "destination_airport": "LIS",
             "price": 2890, "airline": "TP", "flight_number": 88, "departure_at": "2027-01-10T22:10:00-03:00",
             "return_at": "2027-01-24T11:30:00+00:00", "transfers": 0, "return_transfers": 0,
             "link": "/search/SAO1001LIS24011"}
        n = normalizar(t, "BRL")
        self.assertEqual(n["ida"], "2027-01-10")
        self.assertEqual(n["volta"], "2027-01-24")
        self.assertEqual(n["link_aviasales"], "https://www.aviasales.com/search/SAO1001LIS24011")
        self.assertIsNone(normalizar({**t, "return_at": None}))

    def test_veredito(self):
        self.assertEqual(veredito(3000, {"menor_preco": 3100, "nivel": "low"}, 0.15), "confirmado")
        self.assertEqual(veredito(3000, {"menor_preco": 3600, "nivel": "low"}, 0.15), "preco_mudou")
        self.assertEqual(veredito(3000, {"menor_preco": 3000, "nivel": "typical", "faixa_tipica": [2800, 4000]}, 0.15),
                         "nao_confirmado")
        self.assertEqual(veredito(3000, {"menor_preco": 2700, "nivel": "typical", "faixa_tipica": [2800, 4000]}, 0.15),
                         "confirmado")
        self.assertEqual(veredito(3000, {"menor_preco": None}, 0.15), "sem_resposta")


class TestConfigESite(unittest.TestCase):
    def test_rotas_e_agenda(self):
        config = carregar_config()
        self.assertEqual(len(list(rotas(config, "todas"))), 56)
        self.assertEqual(len(list(rotas(config, "auto", hora_utc=6))), 14)  # só São Paulo
        self.assertEqual(len(list(rotas(config, "auto", hora_utc=12))), 56)
        self.assertEqual(len(meses_da_busca(config)), 9)

    def test_site_gera_html(self):
        config = carregar_config()
        agora = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
        a = {"id": "SAO-LIS-2027-01-25-2027-02-03", "rota": "SAO-LIS", "ida": "2027-01-25", "volta": "2027-02-03",
             "preco": 3000.0, "preco_normal": 5000, "desconto": 0.4, "visto_em": agora.isoformat(),
             "primeiro_em": agora.isoformat(), "conferencia": None, "curadoria": None}
        descartado = {**a, "id": "x", "curadoria": {"status": "descartado"}}
        estado = {"ativos": {a["id"]: a, "x": descartado}, "expirados": {}}
        with tempfile.TemporaryDirectory() as tmp:
            destino = site.gerar(estado, {}, config, indice_cidades(config), agora, destino=Path(tmp) / "i.html")
            html = destino.read_text(encoding="utf-8")
        dados = json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
        self.assertEqual(len(dados["achados"]), 1)
        self.assertEqual(dados["achados"][0]["status"], "a_conferir")
        self.assertIn("google.com/travel/flights", dados["achados"][0]["link_google"])


if __name__ == "__main__":
    unittest.main()
