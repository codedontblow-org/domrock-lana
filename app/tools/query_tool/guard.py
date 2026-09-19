import sqlglot
from sqlglot import exp

TABELAS_PERMITIDAS = {"vendedor", "produto", "venda"}


class SqlInseguro(Exception):
    """Exceção levantada quando uma consulta SQL não passa pela validação."""
    pass


def validar(sql: str) -> str:
    """Valida uma consulta SQL e devolve sua versão normalizada."""

    # Converte o texto SQL em uma lista de árvores sintáticas, uma por comando.
    try:
        comandos = [c for c in sqlglot.parse(sql, dialect="sqlite") if c is not None]
    except Exception as e:
        raise SqlInseguro(f"SQL não pôde ser interpretado: {e}")

    # Permite exatamente um comando, evitando várias operações na mesma entrada.
    if len(comandos) != 1:
        raise SqlInseguro(f"Apenas um comando SQL por vez é permitido (encontrados: {len(comandos)}).")

    # Seleciona a árvore sintática raiz do único comando encontrado.
    arvore_sql = comandos[0]

    # Garante apenas SELECT.
    if not isinstance(arvore_sql, exp.Select):
        raise SqlInseguro(f"Só SELECT é permitido. Recebido: {type(arvore_sql).__name__}")

    # Procura operações de escrita ou alterações escondidas dentro da árvore.
    comandos_perigosos = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter)
    if list(arvore_sql.find_all(*comandos_perigosos)):
        raise SqlInseguro("Comando de escrita encontrado dentro da consulta.")

    # Extrai os nomes das tabelas presentes na árvore e compara com a lista segura.
    cte_names = {cte.alias_or_name.lower() for cte in arvore_sql.find_all(exp.CTE)}
    tabelas_usadas = {t.name.lower() for t in arvore_sql.find_all(exp.Table)}
    fora_da_lista = tabelas_usadas - TABELAS_PERMITIDAS - cte_names
    if fora_da_lista:
        raise SqlInseguro(f"Tabela não autorizada: {fora_da_lista}")

    # Gera novamente o SQL a partir da árvore, em formato SQLite normalizado.
    return arvore_sql.sql(dialect="sqlite")