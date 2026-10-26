from app.core.trilha import competencia_por_extenso, competencias_por_extenso


def test_competencia_por_extenso() -> None:
    assert competencia_por_extenso("2025-10") == "out/2025"
    assert competencias_por_extenso(["2025-11", "2025-12"]) == "nov/2025, dez/2025"


def test_competencia_fora_do_formato_volta_igual() -> None:
    assert competencia_por_extenso("2025-13") == "2025-13"
