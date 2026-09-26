"""Apuração base (baseline): a comissão sem a regra nova, 100% determinística.

Regras base da Sprint 1: % da combinação marca + cargo sobre a venda do mês da matrícula;
o gerente (cargo 150) recebe sobre a venda total da loja, incluindo a própria.
Proporcional de admissão/demissão fica para a Sprint 2.
"""
import pandas as pd

from app.simulacao.bases import BasesSimulacao

CARGO_GERENTE = "150"
CHAVE_APURACAO = ["matricula", "competencia"]
COLUNAS_APURACAO = [
    "matricula", "competencia", "cod_loja", "cod_marca", "cod_cargo",
    "base_calculo", "pct_comiss", "comissao",
]


class BaselineError(ValueError):
    """Dado insuficiente para apurar o baseline."""


def calcular_baseline(bases: BasesSimulacao) -> pd.DataFrame:
    """Uma linha por matrícula e competência. Ex.: calcular_baseline(bases)["comissao"].sum()"""
    apuracao = _juntar_vendas(bases.rh, bases.vendas)
    apuracao = _juntar_percentuais(apuracao, bases.comissoes)
    eh_gerente = apuracao["cod_cargo"] == CARGO_GERENTE
    apuracao["base_calculo"] = apuracao["venda_loja"].where(eh_gerente, apuracao["venda_matricula"])
    apuracao["comissao"] = (apuracao["base_calculo"] * apuracao["pct_comiss"] / 100).round(2)
    return apuracao[COLUNAS_APURACAO].sort_values(CHAVE_APURACAO, ignore_index=True)


def _juntar_vendas(rh: pd.DataFrame, vendas: pd.DataFrame) -> pd.DataFrame:
    por_matricula = _somar_vendas(vendas, CHAVE_APURACAO, "venda_matricula")
    por_loja = _somar_vendas(vendas, ["cod_loja", "competencia"], "venda_loja")
    apuracao = rh.merge(por_matricula, on=CHAVE_APURACAO, how="left")
    apuracao = apuracao.merge(por_loja, on=["cod_loja", "competencia"], how="left")
    return apuracao.fillna({"venda_matricula": 0.0, "venda_loja": 0.0})


def _somar_vendas(vendas: pd.DataFrame, chave: list[str], nome: str) -> pd.DataFrame:
    return vendas.groupby(chave, as_index=False)["vlr_venda"].sum().rename(
        columns={"vlr_venda": nome}
    )


def _juntar_percentuais(apuracao: pd.DataFrame, comissoes: pd.DataFrame) -> pd.DataFrame:
    juntos = apuracao.merge(comissoes, on=["cod_marca", "cod_cargo"], how="left")
    sem_pct = juntos[juntos["pct_comiss"].isna()][["cod_marca", "cod_cargo"]].drop_duplicates()
    if not sem_pct.empty:
        raise BaselineError(
            f"Sem % de comissão para marca/cargo {sem_pct.values.tolist()}; "
            "esperado uma linha em marca_cargo para cada combinação do RH"
        )
    return juntos
