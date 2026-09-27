"""Asserções determinísticas sobre o resultado do código gerado.

O executor garante que o código não é perigoso; estas verificações pegam o código que
roda sem erro e devolve número errado (ARCHITECTURE.md §1.4 do Synapse, adaptado).
"""
import math

import pandas as pd

from app.simulacao.bases import competencias_do_periodo
from app.simulacao.baseline import CHAVE_APURACAO
from app.tools.regra_tool.dtos import ParametrosSimulacao

TOLERANCIA_CENTAVO = 0.011
COLUNAS_CONTRIBUICAO = ["matricula", "competencia", "elemento_ref", "delta"]


class AssercaoViolada(ValueError):
    """O resultado do código gerado viola uma invariante; a mensagem diz qual e com que valor."""


def conferir_resultado(
    base: pd.DataFrame, simulada: pd.DataFrame, contribuicoes: pd.DataFrame,
    parametros: ParametrosSimulacao,
) -> pd.DataFrame:
    """Devolve a comparação linha a linha (com `diferenca`) ou levanta `AssercaoViolada`."""
    _conferir_colunas(simulada, CHAVE_APURACAO + ["comissao"], "apuracao_simulada")
    comparacao = _comparar_linhas(base, simulada)
    _conferir_sem_negativo(comparacao)
    _conferir_contribuicoes(comparacao, _normalizar_contribuicoes(contribuicoes))
    _conferir_escopo(comparacao, parametros)
    return comparacao


def _conferir_colunas(tabela: pd.DataFrame, colunas: list[str], nome: str) -> None:
    faltando = [c for c in colunas if c not in tabela.columns]
    if faltando:
        raise AssercaoViolada(f"{nome} sem colunas {faltando}; colunas recebidas {list(tabela.columns)}")


def _comparar_linhas(base: pd.DataFrame, simulada: pd.DataFrame) -> pd.DataFrame:
    simulada = simulada.astype({"matricula": str, "competencia": str})
    if simulada.duplicated(CHAVE_APURACAO).any() or len(simulada) != len(base):
        raise AssercaoViolada(
            f"apuracao_simulada tem {len(simulada)} linhas (duplicadas: "
            f"{int(simulada.duplicated(CHAVE_APURACAO).sum())}); esperado {len(base)}, uma por matrícula/competência"
        )
    comparacao = base.merge(
        simulada[CHAVE_APURACAO + ["comissao"]], on=CHAVE_APURACAO, how="left", suffixes=("", "_simulada")
    )
    if comparacao["comissao_simulada"].isna().any():
        raise AssercaoViolada("apuracao_simulada não tem as mesmas (matricula, competencia) do baseline")
    comparacao["diferenca"] = (comparacao["comissao_simulada"] - comparacao["comissao"]).round(2)
    return comparacao


def _conferir_sem_negativo(comparacao: pd.DataFrame) -> None:
    invalidas = comparacao[~comparacao["comissao_simulada"].map(_numero_valido)]
    if not invalidas.empty:
        amostra = invalidas[CHAVE_APURACAO + ["comissao_simulada"]].head(3).to_dict("records")
        raise AssercaoViolada(f"Comissão negativa ou não finita em {len(invalidas)} linhas, ex.: {amostra}")


def _numero_valido(valor: float) -> bool:
    return math.isfinite(valor) and valor >= 0


def _normalizar_contribuicoes(contribuicoes: pd.DataFrame) -> pd.DataFrame:
    if contribuicoes.empty:
        return pd.DataFrame(columns=COLUNAS_CONTRIBUICAO)
    _conferir_colunas(contribuicoes, COLUNAS_CONTRIBUICAO, "contribuicoes")
    return contribuicoes.astype({"matricula": str, "competencia": str, "delta": float})


def _conferir_contribuicoes(comparacao: pd.DataFrame, contribuicoes: pd.DataFrame) -> None:
    declarado = contribuicoes.groupby(CHAVE_APURACAO, as_index=False)["delta"].sum()
    juntos = comparacao.merge(declarado, on=CHAVE_APURACAO, how="left").fillna({"delta": 0.0})
    divergentes = juntos[(juntos["diferenca"] - juntos["delta"]).abs() > TOLERANCIA_CENTAVO]
    if not divergentes.empty:
        amostra = divergentes[CHAVE_APURACAO + ["diferenca", "delta"]].head(3).to_dict("records")
        raise AssercaoViolada(
            f"Soma das contribuicoes difere da mudança de comissão em {len(divergentes)} linhas, ex.: {amostra}"
        )


def _conferir_escopo(comparacao: pd.DataFrame, parametros: ParametrosSimulacao) -> None:
    fora = ~comparacao["cod_marca"].isin(parametros.marcas_alvo) | ~comparacao["cod_cargo"].isin(parametros.cargos_alvo)
    fora = fora | ~comparacao["competencia"].isin(
        competencias_do_periodo(parametros.data_inicio, parametros.data_fim)
    )
    alteradas_fora = comparacao[fora & (comparacao["diferenca"] != 0)]
    if not alteradas_fora.empty:
        amostra = alteradas_fora[["matricula", "cod_marca", "cod_cargo", "competencia", "diferenca"]].head(3)
        raise AssercaoViolada(
            f"Regra alterou {len(alteradas_fora)} linhas fora de marcas {parametros.marcas_alvo}, "
            f"cargos {parametros.cargos_alvo} ou período; ex.: {amostra.to_dict('records')}"
        )


DICA_GERENTE = (
    "Lembre: o gerente (cod_cargo 150) recebe sobre a venda TOTAL da loja no período; "
    "não filtre as vendas por cod_cargo antes de somar por loja."
)


def conferir_contra_referencia(comparacao: pd.DataFrame, referencia: pd.DataFrame) -> None:
    """Compara a diferença por matrícula com o cálculo determinístico do mesmo contrato.

    Pega o código que passa nas outras asserções mas calcula errado (ex.: gerente sobre a
    própria venda em vez da venda da loja).
    """
    juntos = comparacao.merge(
        referencia[CHAVE_APURACAO + ["diferenca"]], on=CHAVE_APURACAO, suffixes=("", "_esperada")
    )
    divergentes = juntos[(juntos["diferenca"] - juntos["diferenca_esperada"]).abs() > TOLERANCIA_CENTAVO]
    if divergentes.empty:
        return
    amostra = divergentes[["matricula", "cod_cargo", "competencia", "diferenca", "diferenca_esperada"]].head(3)
    raise AssercaoViolada(
        f"Resultado diverge do cálculo de conferência em {len(divergentes)} linhas, "
        f"ex.: {amostra.to_dict('records')}. {DICA_GERENTE}"
    )

