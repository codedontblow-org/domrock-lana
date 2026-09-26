import pytest

from app.tools.code_tool.codigo import CodigoInvalidoError, extrair_codigo, validar_codigo

VALIDO = "import pandas as pd\n\ndef aplicar_regra(bases, apuracao_base, competencias):\n    return {}\n"


def test_extrair_codigo_devolve_o_unico_bloco_python() -> None:
    assert extrair_codigo(f"Segue:\n```python\n{VALIDO}```\nfim") == VALIDO


def test_extrair_codigo_rejeita_resposta_sem_bloco() -> None:
    with pytest.raises(CodigoInvalidoError, match="encontrados 0"):
        extrair_codigo(VALIDO)


@pytest.mark.parametrize(
    ("fonte", "trecho"),
    [
        ("import os\n" + VALIDO, "'os'"),
        ("from subprocess import run\n" + VALIDO, "'subprocess'"),
        (VALIDO + "open('/etc/passwd')\n", "'open'"),
        (VALIDO + "x = ().__class__\n", "__class__"),
        (VALIDO + "eval('1')\n", "'eval'"),
        ("def aplicar_regra(bases):\n    return {}\n", "aplicar_regra(bases, apuracao_base"),
        ("def aplicar_regra(:\n", "não é Python válido"),
    ],
)
def test_validar_codigo_recusa_codigo_inseguro_ou_fora_do_contrato(fonte: str, trecho: str) -> None:
    with pytest.raises(CodigoInvalidoError, match=None) as erro:
        validar_codigo(fonte)

    assert trecho in str(erro.value)
