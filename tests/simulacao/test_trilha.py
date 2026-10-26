import re

from app.simulacao.bases import SQL_DAS_BASES, TABELAS_DAS_BASES
from app.simulacao.trilha import Cronometro


def test_cronometro_soma_o_tempo_do_mesmo_passo_entre_tentativas() -> None:
    cronometro = Cronometro()

    for _ in range(2):
        with cronometro.medir("gerar_codigo"):
            pass

    assert list(cronometro.tempos) == ["gerar_codigo"] and cronometro.tempos["gerar_codigo"] >= 0


def test_tabelas_da_trilha_sao_as_que_o_sql_das_bases_le() -> None:
    lidas = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)", SQL_DAS_BASES))

    assert lidas == set(TABELAS_DAS_BASES)
