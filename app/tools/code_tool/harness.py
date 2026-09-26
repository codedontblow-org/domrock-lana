"""Executa o `aplicar_regra` gerado dentro do subprocesso isolado.

Roda como script (`python -I harness.py`): lê um payload JSON do stdin e escreve um envelope
JSON de uma linha no stdout. Não importa nada de `app` de propósito: o subprocesso só vê
a biblioteca padrão e o pandas.
"""
import json
import sys
import traceback
from io import StringIO

import pandas as pd

COLUNAS_DATA = ("data_venda", "data_admissao", "data_demissao")
CHAVES_RETORNO = ("apuracao_simulada", "contribuicoes")
LIMITE_TRACEBACK = 2000


class RetornoInvalidoError(TypeError):
    """`aplicar_regra` devolveu algo fora do contrato."""


def ler_tabela(registros_json: str) -> pd.DataFrame:
    tabela = pd.read_json(StringIO(registros_json), orient="records", dtype=False)
    for coluna in COLUNAS_DATA:
        if coluna in tabela.columns:
            tabela[coluna] = pd.to_datetime(tabela[coluna])
    return tabela


def carregar_regra(fonte: str):
    namespace: dict[str, object] = {"__name__": "regra"}
    exec(compile(fonte, "regra.py", "exec"), namespace)
    return namespace["aplicar_regra"]


def validar_retorno(retorno: object) -> dict[str, pd.DataFrame]:
    if not isinstance(retorno, dict):
        raise RetornoInvalidoError(f"Esperado dict com {CHAVES_RETORNO}, recebido {type(retorno).__name__}")
    for chave in CHAVES_RETORNO:
        if not isinstance(retorno.get(chave), pd.DataFrame):
            raise RetornoInvalidoError(f"Esperado DataFrame em '{chave}', recebido {type(retorno.get(chave)).__name__}")
    return retorno


def executar(payload: dict) -> dict:
    bases = {nome: ler_tabela(registros) for nome, registros in payload["bases"].items()}
    apuracao_base = ler_tabela(payload["apuracao_base"])
    aplicar_regra = carregar_regra(payload["fonte"])
    retorno = validar_retorno(aplicar_regra(bases, apuracao_base.copy(), list(payload["competencias"])))
    return {
        "status": "ok",
        **{chave: retorno[chave].to_json(orient="records", date_format="iso") for chave in CHAVES_RETORNO},
    }


def main() -> None:
    payload = json.load(sys.stdin)
    try:
        envelope = executar(payload)
    except Exception as erro:  # o código gerado pode levantar qualquer coisa
        envelope = {
            "status": "erro_codigo",
            "mensagem": f"{type(erro).__name__}: {erro}",
            "traceback": traceback.format_exc()[-LIMITE_TRACEBACK:],
        }
    sys.stdout.write(json.dumps(envelope))


if __name__ == "__main__":
    main()
