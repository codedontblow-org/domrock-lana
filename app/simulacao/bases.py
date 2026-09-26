"""Carga das bases de uma simulação a partir do Postgres do backend.

As linhas nunca passam pelo contexto da LLM: vão para o baseline e para o executor.
Competência é sempre texto `YYYY-MM`; `data_venda` guarda a data real (em nov/25 há vendas
de 24 a 28/11), enquanto loja e cargo são vínculos mensais (dia 1º).
"""
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import pandas as pd

SQL_RH = """
SELECT f.matricula, to_char(fl.date_ref, 'YYYY-MM') AS competencia,
       l.cod_loja, m.cod_marca, c.cod_cargo,
       f.data_admissao, f.data_demissao
FROM funcionario f
JOIN funcionario_loja fl ON fl.funcionario_id = f.id
JOIN loja l ON l.id = fl.loja_id
JOIN marca m ON m.id = l.marca_id
JOIN funcionario_cargo fc ON fc.funcionario_id = f.id AND fc.date_ref = fl.date_ref
JOIN cargo c ON c.id = fc.cargo_id
WHERE to_char(fl.date_ref, 'YYYY-MM') = ANY(%(competencias)s)
"""

SQL_VENDAS = """
SELECT f.matricula, to_char(v.date_ref, 'YYYY-MM') AS competencia,
       v.date_ref AS data_venda, v.vlr_venda::float8 AS vlr_venda,
       l.cod_loja, m.cod_marca, c.cod_cargo
FROM venda v
JOIN funcionario f ON f.id = v.funcionario_id
JOIN funcionario_loja fl ON fl.funcionario_id = v.funcionario_id
     AND fl.date_ref = date_trunc('month', v.date_ref)::date
JOIN loja l ON l.id = fl.loja_id
JOIN marca m ON m.id = l.marca_id
JOIN funcionario_cargo fc ON fc.funcionario_id = v.funcionario_id AND fc.date_ref = fl.date_ref
JOIN cargo c ON c.id = fc.cargo_id
WHERE to_char(v.date_ref, 'YYYY-MM') = ANY(%(competencias)s)
"""

# A tabela de % é única (não varia por competência); vale a importação mais recente.
SQL_COMISSOES = """
SELECT m.cod_marca, c.cod_cargo, mc.pct_comiss::float8 AS pct_comiss
FROM marca_cargo mc
JOIN marca m ON m.id = mc.marca_id
JOIN cargo c ON c.id = mc.cargo_id
WHERE mc.date_ref = (SELECT max(date_ref) FROM marca_cargo)
"""

COLUNAS_DATA = ("data_venda", "data_admissao", "data_demissao")


@dataclass(frozen=True)
class BasesSimulacao:
    """As três bases de um período: `rh`, `vendas` e `comissoes` (pct literal: 2.5 = 2,5%)."""

    rh: pd.DataFrame
    vendas: pd.DataFrame
    comissoes: pd.DataFrame

    def como_dict(self) -> dict[str, pd.DataFrame]:
        return {"rh": self.rh, "vendas": self.vendas, "comissoes": self.comissoes}


class FonteBases(Protocol):
    def carregar(self, competencias: list[str]) -> BasesSimulacao: ...


class ConexaoDb(Protocol):
    def cursor(self) -> Any: ...


class PostgresFonteBases:
    """Lê as bases do Postgres. Ex.: PostgresFonteBases(get_connection).carregar(["2025-10"])"""

    def __init__(self, abrir_conexao: Callable[[], AbstractContextManager[ConexaoDb]]) -> None:
        self._abrir_conexao = abrir_conexao

    def carregar(self, competencias: list[str]) -> BasesSimulacao:
        parametros = {"competencias": competencias}
        with self._abrir_conexao() as conexao:
            return BasesSimulacao(
                rh=_consultar(conexao, SQL_RH, parametros),
                vendas=_consultar(conexao, SQL_VENDAS, parametros),
                comissoes=_consultar(conexao, SQL_COMISSOES, {}),
            )


def _consultar(conexao: ConexaoDb, sql: str, parametros: dict[str, Any]) -> pd.DataFrame:
    with conexao.cursor() as cursor:
        cursor.execute(sql, parametros)
        colunas = [coluna[0] for coluna in cursor.description]
        tabela = pd.DataFrame(cursor.fetchall(), columns=colunas)
    return _tipar_datas(tabela)


def _tipar_datas(tabela: pd.DataFrame) -> pd.DataFrame:
    for coluna in COLUNAS_DATA:
        if coluna in tabela.columns:
            tabela[coluna] = pd.to_datetime(tabela[coluna])
    return tabela


def competencias_do_periodo(inicio: date, fim: date) -> list[str]:
    """Meses tocados pelo período. Ex.: (2025-11-24, 2025-12-05) -> ["2025-11", "2025-12"]"""
    meses = pd.period_range(start=inicio, end=fim, freq="M")
    return [str(mes) for mes in meses]
