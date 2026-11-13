# Motor de achados do Clube VIP

Versão de teste do motor (13 a 27/11/2026, com a Miriã e o Maicky). Varre 56 rotas
(São Paulo, Rio, Belo Horizonte e Brasília para 14 destinos internacionais), compara cada preço
com o preço normal da rota, confere os achados no Google Flights e publica num site.

## Como funciona

1. **Coleta** (`motor/fontes/travelpayouts.py`): menores preços de ida e volta por data, de 1 a 9 meses à frente,
   encontrados por usuários da Aviasales nas últimas 48 horas. Grátis.
2. **Preço normal** (`motor/deteccao.py`): mediana de todas as datas da rota, combinada com as medianas
   diárias dos últimos 30 dias conforme o histórico cresce (`data/historico/`).
3. **Achado**: 30% ou mais abaixo do normal. 50% ou mais vira "possível erro tarifário".
   No máximo 1 por mês de saída e 3 por rota.
4. **Conferência** (`motor/conferencia.py`): com `SERPAPI_KEY`, até 3 achados por execução são checados no
   Google Flights (preço atual e se o Google considera baixo). Sem a chave, ficam "a conferir".
5. **Site** (`docs/index.html`): página única com filtros. O robô do GitHub roda a cada 6 horas.

As rotas, os cortes e os limites ficam em `config/rotas.json`.

## Primeira vez (no seu computador)

1. Crie a conta na [Travelpayouts](https://www.travelpayouts.com), conecte o programa da Aviasales e copie o
   token em Ferramentas > API.
2. Copie `.env.example` para `.env` e cole o token em `TRAVELPAYOUTS_TOKEN=`.
3. Opcional: crie conta na [SerpApi](https://serpapi.com) (plano grátis, 250 buscas por mês) e cole a chave em `SERPAPI_KEY=`.
4. Rode, na pasta do projeto:

```bash
python3 -m motor diagnostico          # testa o token e mostra quantos preços vêm para São Paulo → Lisboa
python3 -m motor rodar --todas        # primeira varredura completa (uns 3 minutos)
python3 -m motor cobertura            # quanto cada rota rendeu
open docs/index.html                  # o site, do jeito que eles vão ver
```

Se o `diagnostico` mostrar bem mais preços com `mercado=br`, troque `"mercado": null` por `"mercado": "br"` em `config/rotas.json`.

## Rotina diária (10 minutos)

- Abra o site e confira os achados "a conferir" clicando em "Ver no Google Flights".
- Marque o resultado:

```bash
python3 -m motor marcar SAO-LIS-2027-01-25-2027-02-03 conferido
python3 -m motor marcar SAO-LIS-2027-01-25-2027-02-03 descartado --nota "preço já subiu"
```

Os IDs aparecem em `data/achados.json`. No fim do teste: `python3 -m motor relatorio`.

## Colocar no ar (GitHub)

1. Crie um repositório e envie esta pasta (o `.env` fica de fora pelo `.gitignore`).
2. Em Settings > Secrets and variables > Actions, crie `TRAVELPAYOUTS_TOKEN` e, se tiver, `SERPAPI_KEY`.
3. Em Settings > Pages, escolha "Deploy from a branch", branch `main`, pasta `/docs`.
4. Em Actions > Motor de achados, rode uma vez com "Varrer todas as rotas agora".

O GitHub Pages é grátis em repositório público. Em repositório privado, precisa do plano GitHub Pro.
O site tem `noindex`, mas qualquer pessoa com o link consegue abrir.

## Testes

```bash
python3 -m unittest discover -s tests -v
python3 -m motor exemplo               # prévia do site com dados fictícios em data/previa_exemplo.html
```
