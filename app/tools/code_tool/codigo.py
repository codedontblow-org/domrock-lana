"""Extração e validação estática do código que a LLM devolve.

O código é dado não confiável: aqui ele só é lido com `ast.parse`, nunca executado.
Executar é trabalho exclusivo do `SubprocessRunner`. Inspirado no `codigo_gerado.py` do
Synapse (Titus System), com allowlist de imports e bloqueio de nomes perigosos.
"""
import ast
import re

BLOCO_PYTHON = re.compile(r"```python[ \t]*\n(.*?)```", re.DOTALL)
PARAMETROS_REGRA = ["bases", "apuracao_base", "competencias"]
IMPORTS_PERMITIDOS = frozenset({"pandas", "numpy", "math", "datetime"})
NOMES_PROIBIDOS = frozenset({
    "open", "exec", "eval", "compile", "__import__", "input", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "breakpoint", "exit", "quit",
})


class CodigoInvalidoError(ValueError):
    """A resposta da LLM não traz um `aplicar_regra` válido e seguro."""


def extrair_codigo(resposta: str) -> str:
    """Devolve o fonte do único bloco ```python da resposta, já validado.

    Ex.: extrair_codigo("```python\\ndef aplicar_regra(bases, apuracao_base, competencias): ...```")
    """
    blocos = BLOCO_PYTHON.findall(resposta)
    if len(blocos) != 1:
        raise CodigoInvalidoError(f"Esperado exatamente 1 bloco ```python, encontrados {len(blocos)}")
    fonte: str = blocos[0]
    validar_codigo(fonte)
    return fonte


def validar_codigo(fonte: str) -> None:
    """Levanta `CodigoInvalidoError` se o fonte não compila, é inseguro ou foge da assinatura."""
    try:
        modulo = ast.parse(fonte)
    except SyntaxError as erro:
        raise CodigoInvalidoError(f"Código gerado não é Python válido: linha {erro.lineno}: {erro.msg}") from None
    for no in ast.walk(modulo):
        _validar_no(no)
    if not _define_aplicar_regra(modulo):
        raise CodigoInvalidoError(
            f"Código gerado não define aplicar_regra({', '.join(PARAMETROS_REGRA)}) no nível do módulo"
        )


def _validar_no(no: ast.AST) -> None:
    if isinstance(no, ast.Import):
        _validar_imports([alias.name for alias in no.names])
    elif isinstance(no, ast.ImportFrom):
        _validar_imports([no.module or ""])
    elif isinstance(no, ast.Name) and no.id in NOMES_PROIBIDOS:
        raise CodigoInvalidoError(f"Uso proibido de '{no.id}' na linha {no.lineno}")
    elif isinstance(no, ast.Attribute) and no.attr.startswith("__"):
        raise CodigoInvalidoError(f"Acesso proibido a atributo dunder '{no.attr}' na linha {no.lineno}")


def _validar_imports(modulos: list[str]) -> None:
    for modulo in modulos:
        raiz = modulo.split(".")[0]
        if raiz not in IMPORTS_PERMITIDOS:
            raise CodigoInvalidoError(
                f"Import proibido: '{modulo}'; permitidos: {sorted(IMPORTS_PERMITIDOS)}"
            )


def _define_aplicar_regra(modulo: ast.Module) -> bool:
    for no in modulo.body:
        if isinstance(no, ast.FunctionDef) and no.name == "aplicar_regra":
            argumentos = no.args
            nomes = [arg.arg for arg in [*argumentos.posonlyargs, *argumentos.args]]
            return nomes == PARAMETROS_REGRA and argumentos.vararg is None and argumentos.kwarg is None
    return False
