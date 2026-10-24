# A6-74 — Percentuais vigentes por marca e cargo

`POST /simulacao` aceita `campanhas` junto à ficha. O backend fornece as versões
aprovadas e pendentes que cruzam período, marca e cargo, além das fontes da
especificação. Requisições antigas sem esse campo continuam aceitas (contexto vazio).
O endpoint da Lana é interno: o contexto confiável deve ser montado pelo backend.

## Cálculo

`app/simulacao/vigencia.py` faz a composição determinística, sem depender da LLM:

1. `% base`: `marca_cargo.pct_comiss` da importação mais recente, já selecionada
   por `PostgresFonteBases`. `2.5` significa 2,5%.
2. Em cada dia, substitui a base pela última `SUBSTITUICAO` aprovada que cubra
   a marca/cargo. A taxa pode ser absoluta ou referenciar outra marca, no mesmo cargo.
3. Soma os percentuais das campanhas `ACRESCIMO` aprovadas que cubram aquele dia.
4. Aplica o novo acréscimo somente às vendas dentro da janela da ficha.
   O custo adicional é a diferença em relação à comissão que já considera as aprovadas.
5. `AGUARDANDO_APROVACAO` só gera conflito; não altera percentuais ou valores.

As datas são inclusivas. Substituições sobrepostas geram aviso; a última aprovação
vence. Empates de timestamp usam o ID como desempate estável, explicitado no aviso.
Campanhas da especificação sem decisão humana antecedem as aprovações registradas.
A soma dos acréscimos segue a regra **provisória A6-73**, sem teto de percentual.

A comissão vigente é apurada com `Decimal` pelas datas reais de venda e arredondada
para centavos por matrícula/competência (`ROUND_HALF_EVEN`). Gerentes (150) usam
as vendas totais da loja. O executor existente aplica o delta da nova campanha,
com seu arredondamento monetário por matrícula/competência. Totais continuam sendo
mensais; o contexto contém as campanhas que cruzam a janela solicitada. Não é um
novo fechamento completo de todas as campanhas do mês, nem uma apuração de prêmios
fixos ou afastamentos. As ressalvas anteriores da simulação continuam válidas.

## Resposta

- `comissoes_periodo`: um trecho por marca/cargo e intervalo de composição constante.
  Campos: `id`, `marca`, `cargo`, `inicio`, `fim`, `base`, `vigente`, `comCampanha`,
  `historico`, `avisos`. Os limites também preservam mudanças de fonte, mesmo que
  duas composições resultem na mesma taxa.
- `historico`: `id`, `nome`, `tipo`, `inicio`, `fim`, `percentual`, `acrescimo`,
  `aplicada`, `autor`, `aprovador`, `aprovadoEm`, `justificativa`, `origem`.
  Uma substituição vencida permanece na explicação com `aplicada: false`;
  `acrescimo` é nulo para substituições, cujo valor está em `percentual`.
- `conflitos`: uma entrada por campanha/marca, cargos intersectados e intervalo
  sobreposto. Inclui `tipo` e `status` para distinguir pendência e substituição.
- `trilha.campanhas`: fontes aplicadas nos trechos, com os dados recebidos do backend.
  Pendentes e substituições vencidas não são fontes do percentual efetivo.

Aprovadas normais exigem data de aprovação com fuso. IDs duplicados, taxa base
inválida/ausente ou marca de referência sem taxa interrompem a simulação com erro,
sem devolver resultado parcial. Fontes `ESPECIFICACAO` podem ter metadados humanos nulos.

Os nomes `comissoes_periodo` e os campos de apresentação seguem a integração prevista
pela A6-75. O backend persiste o JSON inteiro e congela a versão na submissão.
Nenhuma nova dependência ou configuração foi adicionada.

## Exemplos e testes

```bash
python -m pip install -r requirements-dev.txt
AI_PROVIDER=GEMINI AI_MODEL=modelo-de-teste GEMINI_API_KEY=chave-de-teste python -m pytest tests/simulacao -q
```

Os testes usam fonte de dados e explicador falsos; não chamam uma LLM ou banco real.
`test_vigencia.py` cobre os cinco critérios do card: trechos 24/11 e 25–30/11,
interseções até dezembro, outubro sem campanha, pendente C sem efeito na taxa e
substituição 3g em setembro. Também cobre aprovação mais recente, escopo e entradas
inválidas. O teste com o executor real confirma comissão vigente de R$ 195,00,
simulada de R$ 210,00 e custo incremental de R$ 15,00 para +0,5% sobre R$ 3.000,00.
