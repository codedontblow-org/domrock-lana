"""Prompt da geração de código da regra (A6-37).

Estrutura inspirada no `regrafn.md` do Synapse: contrato da função, esquema anotado,
convenções que quebram joins em silêncio e amostras de 10 linhas.
"""
import json

from app.tools.code_tool.dtos import ContextoGeracao

CONTRATO = """
Escreva UM arquivo Python com UMA função pública, exatamente com esta assinatura:

    def aplicar_regra(bases, apuracao_base, competencias):

Entrada:
- bases: dict com 3 pandas.DataFrame (cópias; pode ler, não precisa alterar):
  - "rh": matricula, competencia, cod_loja, cod_marca, cod_cargo, data_admissao, data_demissao
    (uma linha por matrícula e competência)
  - "vendas": matricula, competencia, data_venda, vlr_venda, cod_loja, cod_marca, cod_cargo
    (uma linha por venda)
  - "comissoes": cod_marca, cod_cargo, pct_comiss
- apuracao_base: pandas.DataFrame com o baseline JÁ calculado, uma linha por matrícula e
  competência: matricula, competencia, cod_loja, cod_marca, cod_cargo, base_calculo,
  pct_comiss, comissao.
- competencias: lista de "YYYY-MM" do período simulado.

Saída: dict com exatamente duas chaves:
- "apuracao_simulada": cópia de apuracao_base com a MESMA quantidade de linhas e as mesmas
  (matricula, competencia); só a coluna comissao muda onde a regra se aplica.
- "contribuicoes": DataFrame com matricula, competencia, cod_marca, cod_cargo,
  elemento_ref, delta. Uma linha por matrícula/competência que a regra alterou (delta != 0).
  Use elemento_ref = "pct_acrescimo". A soma dos delta de cada matrícula/competência precisa
  ser igual a apuracao_simulada.comissao - apuracao_base.comissao.
"""

CONVENCOES = """
Convenções dos dados (errar isto gera número errado sem erro):
- Códigos (matricula, cod_loja, cod_marca, cod_cargo, competencia) são TEXTO: compare com "30", não 30.
- pct_comiss é percentual literal: 2.5 significa 2,5%. Comissão = base * pct / 100.
- data_venda é datetime64 com a data real da venda. Em 2025-11 há vendas nos dias 24 a 28;
  nos outros meses toda venda está no dia 1º. Filtre janelas de datas por data_venda,
  inclusive nas duas pontas, e nunca pela competencia.
- Regra base já aplicada no baseline: cada cargo recebe pct sobre a própria venda do mês;
  o GERENTE (cod_cargo "150") recebe pct sobre a venda TOTAL da loja no mês. Um acréscimo
  para gerentes, portanto, incide sobre a venda da loja no período da regra: some TODAS as
  vendas da loja (de todos os cargos) na janela; NUNCA filtre as vendas por cod_cargo antes
  dessa soma. Os cargos-alvo filtram quem RECEBE, não quais vendas contam para o gerente.
- Não recalcule o baseline. Parta de apuracao_base e some o efeito da regra.
- Arredonde cada delta com round(…, 2). Comissão nunca pode ficar negativa.
"""

RESTRICOES = """
Restrições (o código é validado e roda isolado; violar derruba a simulação):
- Imports permitidos: pandas, numpy, math, datetime. Nada mais.
- Proibido: open, exec, eval, compile, __import__, getattr/setattr, atributos __dunder__,
  ler arquivos, rede, variáveis de ambiente, print como saída.
- Os parâmetros da regra entram como CONSTANTES no topo do arquivo, não como argumentos.
- Função pura e determinística; pandas 3.x.

Responda apenas com UM bloco ```python contendo o arquivo completo.
"""


def montar_prompt_geracao(contexto: ContextoGeracao, erro_anterior: str | None) -> str:
    """Ex.: montar_prompt_geracao(ContextoGeracao(params, ["2025-10"], amostras), None)"""
    partes = [
        "Você gera o código Python que aplica uma regra de campanha de comissionamento.",
        CONTRATO, CONVENCOES, _secao_regra(contexto), _secao_amostras(contexto.amostras), RESTRICOES,
    ]
    if erro_anterior:
        partes.append(f"A tentativa anterior falhou com este erro. Corrija:\n{erro_anterior}")
    return "\n".join(partes)


def _secao_regra(contexto: ContextoGeracao) -> str:
    parametros = contexto.parametros.model_dump(mode="json", exclude={"meta_vendas", "orcamento_limite"})
    return (
        "Regra confirmada pelo usuário (aplique TODOS os elementos):\n"
        f"{json.dumps(parametros, ensure_ascii=False, indent=2)}\n"
        "pct_acrescimo são pontos percentuais somados ao pct da marca/cargo: 1.0 = +1%.\n"
        "marcas_alvo e cargos_alvo listam quem RECEBE o acréscimo; os demais não mudam.\n"
        f"Competências do período: {contexto.competencias}"
    )


def _secao_amostras(amostras: dict[str, str]) -> str:
    blocos = [f"### {nome} (10 linhas, só para mostrar o formato)\n{csv}" for nome, csv in amostras.items()]
    return "Amostras das tabelas:\n" + "\n".join(blocos)
