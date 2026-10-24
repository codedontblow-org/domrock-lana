# A6-74 — % vigente por marca e cargo, histórico e conflitos

O formato de entrada e de saída é o do contrato da sprint
(`domrock-camplana/docs/contratos-sprint-2.md`): `campanhas` no `POST /simulacao` (4.3),
`comissao_periodo` e `conflitos` no resultado (2.3) e `trilha.campanhas` (2.2).
As regras de sobreposição vêm do estudo A6-73 e do card A6-74. Este documento só explica
onde cada parte está no código.

## De onde vêm as campanhas

- **Do sistema:** o backend manda em `campanhas` as versões aprovadas e as que aguardam
  aprovação que cruzam o período e ao menos uma marca × cargo da ficha, sem a da própria
  conversa (`CampanhaDoSistema`, 4.3). Pedido sem `campanhas` vale como lista vazia.
- **Da especificação:** os itens 2h, 3g, 4g, 5f, 5g, 6f e 6g do `Especificacao.pdf` contam
  como aprovados (estudo A6-73). A Lana carrega sozinha, de
  `app/simulacao/especificacao_2025.json` (`ArquivoEspecificacao`). No A6-77 o arquivo dá
  lugar à tabela, trocando só a implementação de `CatalogoEspecificacao`.
- Item da especificação sai com `campanha_id`, `versao`, `autor`, `aprovador` e
  `aprovada_em` nulos. A 3g ("a marca 10 usa a % da marca 20") usa `marca_referencia`,
  campo interno da Lana: no histórico ela sai com o `pct_novo` já resolvido por cargo.

## Cálculo (`app/simulacao/vigencia.py`)

Para cada dia, marca e cargo, sem LLM e com `Decimal`:

1. **% base** = `marca_cargo.pct_comiss` da importação mais recente (`2.5` = 2,5%).
2. **% do dia** = a base, trocada pela `SUBSTITUICAO` aprovada que cobre o dia; com mais de
   uma, vale a aprovada por último (a especificação, sem data de aprovação, vem antes).
3. **% vigente** = % do dia + soma dos `ACRESCIMO` aprovados que cobrem o dia (soma com
   aviso, regra provisória do estudo A6-73). O aviso é a lista de `conflitos`.
4. Campanha que aguarda aprovação não entra na vigente nem no custo: só em `conflitos`.
5. **Trecho** = intervalo em que a composição fica constante; o início e o fim de cada
   campanha aprovada cortam o período.

`calcular_baseline_vigente` recalcula a comissão atual das linhas tocadas por campanha
aprovada com a data real de cada venda (gerente 150 sobre a venda da loja). O executor
aplica a campanha nova por cima, então `totais.diferenca` é só o custo dela.

Contexto com a mesma versão duas vezes, marca × cargo sem % base ou marca de referência
sem % interrompem a simulação com erro, sem resultado parcial.

## Testes

```bash
python -m pip install -r requirements-dev.txt
AI_PROVIDER=GEMINI AI_MODEL=modelo-de-teste GEMINI_API_KEY=chave-de-teste python -m pytest tests -q
```

- `tests/simulacao/test_vigencia.py`: os cinco critérios do card com os números do
  contrato (exemplos 2 e 3 da seção 2.3), a última substituição vencendo, conflito só com
  marcas e cargos em comum, o item de `campanhas` do 4.3 e o executor real (comissão atual
  de R$ 195,00, simulada de R$ 210,00, custo de R$ 15,00).
- `tests/simulacao/test_especificacao.py`: o catálogo real aplica 2h, 3g, 4g e 5g e faz a
  Black Friday simulada conflitar com o 5f.

Os testes usam fonte de dados, explicador e catálogo falsos; não chamam LLM nem banco.
