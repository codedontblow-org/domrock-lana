"""Executa o `aplicar_regra` gerado dentro do subprocesso isolado.

Roda como script (`python -I -B harness.py <timeout_s>`): lê um payload JSON do stdin e escreve
um envelope JSON de uma linha no canal de resultado. Não importa nada de `app` de propósito:
o subprocesso só vê a biblioteca padrão e o pandas.

Camadas (a validação AST em `codigo.py` é a primeira):
- limites de memória, CPU e escrita em disco aplicados pelo próprio harness, antes de rodar o
  código gerado (sem `preexec_fn`, que não é seguro com threads no processo pai);
- builtins reduzidos e `__import__` que só aceita os módulos permitidos;
- o envelope sai por uma cópia do stdout feita antes do código rodar; o stdout do código gerado
  vai para o stderr, então um `print` esquecido não corrompe o resultado.
"""
import builtins
import json
import os
import resource
import sys
import traceback
from io import StringIO

import pandas as pd

COLUNAS_DATA = ("data_venda", "data_admissao", "data_demissao")
CHAVES_RETORNO = ("apuracao_simulada", "contribuicoes")
LIMITE_TRACEBACK = 2000
LIMITE_MEMORIA_BYTES = 2 * 1024**3
MARGEM_CPU_S = 5
IMPORTS_PERMITIDOS = frozenset({"pandas", "numpy", "math", "datetime"})
BUILTINS_REMOVIDOS = frozenset({
    "open", "exec", "eval", "compile", "input", "breakpoint", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "help", "exit", "quit", "memoryview", "__import__",
})


class RetornoInvalidoError(TypeError):
    """`aplicar_regra` devolveu algo fora do contrato."""


def limitar_recursos(timeout_s: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (LIMITE_MEMORIA_BYTES, LIMITE_MEMORIA_BYTES))
    # Rede de segurança acima do timeout de relógio do runner, para o timeout ser reportado como tal.
    limite_cpu = timeout_s + MARGEM_CPU_S
    resource.setrlimit(resource.RLIMIT_CPU, (limite_cpu, limite_cpu))
    # Bloqueia escrita em arquivos regulares; pipes (stdin/stdout/stderr) não são afetados.
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


def separar_canal_de_resultado():
    """Devolve um arquivo para o envelope e manda o stdout do código gerado para o stderr."""
    canal = os.fdopen(os.dup(sys.stdout.fileno()), "w")
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    return canal


def importar_permitido(nome, globals=None, locals=None, fromlist=(), level=0):
    if level != 0 or nome.split(".")[0] not in IMPORTS_PERMITIDOS:
        raise ImportError(f"Import proibido: '{nome}'; permitidos: {sorted(IMPORTS_PERMITIDOS)}")
    return builtins.__import__(nome, globals, locals, fromlist, level)


def builtins_restritos() -> dict[str, object]:
    restritos = {nome: valor for nome, valor in vars(builtins).items() if nome not in BUILTINS_REMOVIDOS}
    restritos["__import__"] = importar_permitido
    return restritos


def ler_tabela(registros_json: str) -> pd.DataFrame:
    tabela = pd.read_json(StringIO(registros_json), orient="records", dtype=False)
    for coluna in COLUNAS_DATA:
        if coluna in tabela.columns:
            tabela[coluna] = pd.to_datetime(tabela[coluna])
    return tabela


def carregar_regra(fonte: str):
    namespace: dict[str, object] = {"__name__": "regra", "__builtins__": builtins_restritos()}
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
    canal_resultado = separar_canal_de_resultado()
    limitar_recursos(int(sys.argv[1]))
    payload = json.load(sys.stdin)
    try:
        envelope = executar(payload)
    except Exception as erro:  # o código gerado pode levantar qualquer coisa
        envelope = {
            "status": "erro_codigo",
            "mensagem": f"{type(erro).__name__}: {erro}",
            "traceback": traceback.format_exc()[-LIMITE_TRACEBACK:],
        }
    canal_resultado.write(json.dumps(envelope))
    canal_resultado.flush()


if __name__ == "__main__":
    main()
