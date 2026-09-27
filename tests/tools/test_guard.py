import pytest

from app.tools.query_tool.guard import LIMITE_LINHAS, SqlInseguro, validar


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_sleep(30)",
        "SELECT current_setting('data_directory')",
        "SELECT current_user",
        "SELECT version()",
        "SELECT * FROM usuario",
        "SELECT table_name FROM information_schema.tables",
        "DELETE FROM venda",
        "SELECT 1; DROP TABLE venda",
    ],
)
def test_validar_recusa_sql_fora_do_negocio(sql: str) -> None:
    with pytest.raises(SqlInseguro):
        validar(sql)


def test_validar_poe_limit_quando_falta_ou_passa_do_maximo() -> None:
    assert validar("SELECT * FROM venda").endswith(f"LIMIT {LIMITE_LINHAS}")
    assert validar("SELECT * FROM venda LIMIT 100000").endswith(f"LIMIT {LIMITE_LINHAS}")
    assert validar("SELECT * FROM venda LIMIT 5").endswith("LIMIT 5")


def test_validar_aceita_agregacao_com_funcoes_de_data() -> None:
    sql = (
        "SELECT to_char(date_ref, 'YYYY-MM') AS mes, SUM(vlr_venda) AS total "
        "FROM venda WHERE date_ref >= CURRENT_DATE - INTERVAL '1 year' GROUP BY 1"
    )

    assert "SUM(vlr_venda)" in validar(sql)
