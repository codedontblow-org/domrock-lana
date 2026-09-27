"""Montagem e validação determinística da regra.

A LLM só entrega valores; aqui eles viram o contrato (`montar_regra`) e, antes de simular,
a visão tipada (`ler_parametros`). Nenhum valor ausente recebe padrão (backlog, US2).
"""
from datetime import date
from typing import Any

from app.tools.regra_tool.catalogo import (
    CODIGOS_CARGO,
    CODIGOS_MARCA,
    METADADOS,
    OPCOES_POR_CHAVE,
    TODAS_AS_MARCAS,
)
from app.tools.regra_tool.dtos import ParametroRegra, ParametrosSimulacao, RegraCampanha


class RegraInvalidaError(ValueError):
    """A regra não pode ser simulada; `erros` lista cada campo com o valor recebido."""

    def __init__(self, erros: list[str]) -> None:
        super().__init__("; ".join(erros))
        self.erros = erros


def montar_regra(valores: dict[str, Any], raw_prompt: str, rule_id: str) -> RegraCampanha:
    """Monta o contrato a partir dos valores extraídos.

    Ex.: montar_regra({"pct_acrescimo": 1.0}, "…+1%…", "draft-1").faltantes
    -> ["periodo", "marcas_alvo", "cargos_alvo", "meta_vendas", "orcamento_limite"]
    """
    parametros = [_montar_parametro(key, valores.get(key)) for key in METADADOS]
    faltantes = [p.key for p in parametros if _incompleto(p.value)]
    return RegraCampanha(
        rule_id=rule_id, raw_prompt=raw_prompt, parametros=parametros, faltantes=faltantes
    )


def _montar_parametro(key: str, value: Any) -> ParametroRegra:
    label, tipo, categoria = METADADOS[key]
    return ParametroRegra(
        key=key,
        label=label,
        type=tipo,
        categoria=categoria,
        value=None if _vazio(value) else value,
        options=OPCOES_POR_CHAVE.get(key),
    )


def _vazio(value: Any) -> bool:
    return value is None or value == [] or value == {} or value == ""


def _incompleto(value: Any) -> bool:
    """Vazio, ou período com só uma das datas."""
    if isinstance(value, dict):
        return _vazio(value) or any(_vazio(parte) for parte in value.values())
    return _vazio(value)


def ler_parametros(regra: RegraCampanha) -> ParametrosSimulacao:
    """Converte o contrato em parâmetros tipados ou levanta `RegraInvalidaError`.

    Ex.: ler_parametros(regra_black_friday).cargos_alvo -> ["100", "200", "300"]
    """
    valores = {p.key: p.value for p in regra.parametros}
    erros: list[str] = []
    leitores = {
        "periodo": _ler_periodo,
        "pct_acrescimo": _ler_percentual,
        "marcas_alvo": _ler_marcas,
        "cargos_alvo": _ler_cargos,
        "meta_vendas": _ler_valor_monetario,
        "orcamento_limite": _ler_valor_monetario,
    }
    lidos: dict[str, Any] = {}
    for key, leitor in leitores.items():
        try:
            lidos[key] = leitor(key, valores.get(key))
        except (ValueError, TypeError) as erro:
            erros.append(str(erro))
    if erros:
        raise RegraInvalidaError(erros)
    return _para_parametros(lidos)


def _para_parametros(lidos: dict[str, Any]) -> ParametrosSimulacao:
    data_inicio, data_fim = lidos.pop("periodo")
    return ParametrosSimulacao(data_inicio=data_inicio, data_fim=data_fim, **lidos)


def _exigir(key: str, value: Any) -> Any:
    if _vazio(value):
        raise ValueError(f"{key}: obrigatório, recebido {value!r}")
    return value


def _ler_periodo(key: str, value: Any) -> tuple[date, date]:
    periodo = _exigir(key, value)
    try:
        inicio = date.fromisoformat(str(periodo["data_inicio"]))
        fim = date.fromisoformat(str(periodo["data_fim"]))
    except (KeyError, TypeError, ValueError):
        raise ValueError(
            f"{key}: esperado {{data_inicio, data_fim}} em YYYY-MM-DD, recebido {periodo!r}"
        ) from None
    if inicio > fim:
        raise ValueError(f"{key}: data_inicio {inicio} depois de data_fim {fim}")
    return inicio, fim


def _ler_numero_positivo(key: str, value: Any) -> float:
    _exigir(key, value)
    try:
        numero = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key}: esperado número, recebido {value!r}") from None
    if numero <= 0:
        raise ValueError(f"{key}: esperado valor maior que zero, recebido {numero}")
    return numero


def _ler_percentual(key: str, value: Any) -> float:
    pct = _ler_numero_positivo(key, value)
    if pct > 100:
        raise ValueError(f"{key}: esperado percentual até 100, recebido {pct}")
    return pct


def _ler_valor_monetario(key: str, value: Any) -> float:
    return _ler_numero_positivo(key, value)


def _ler_codigos(key: str, value: Any, permitidos: frozenset[str]) -> list[str]:
    valor = _exigir(key, value)
    # A LLM ou o front às vezes mandam um código solto ("30" ou 30) em vez de lista.
    if isinstance(valor, (str, int)):
        valor = [valor]
    if not isinstance(valor, list):
        raise ValueError(f"{key}: esperado lista de códigos, recebido {value!r}")
    codigos = [str(c) for c in valor]
    invalidos = sorted(set(codigos) - permitidos)
    if invalidos:
        raise ValueError(f"{key}: códigos {invalidos} fora de {sorted(permitidos)}")
    return sorted(set(codigos))


def _ler_marcas(key: str, value: Any) -> list[str]:
    marcas = _ler_codigos(key, value, CODIGOS_MARCA)
    if TODAS_AS_MARCAS in marcas:
        return sorted(CODIGOS_MARCA - {TODAS_AS_MARCAS})
    return marcas


def _ler_cargos(key: str, value: Any) -> list[str]:
    return _ler_codigos(key, value, CODIGOS_CARGO)
