import sqlglot
from sqlglot import exp

TABELAS_PERMITIDAS = {
    "marca", "cargo", "funcionario", "loja",
    "marca_cargo", "funcionario_loja", "funcionario_cargo", "venda"
}


LIMITE_LINHAS = 50

# Funções sem tipo próprio no sqlglot (exp.Anonymous) precisam estar nesta lista. Sem ela,
# passavam pg_read_file, pg_sleep, current_setting etc.
FUNCOES_ANONIMAS_PERMITIDAS = frozenset({
    "date_part", "to_char", "to_date", "age", "make_date", "nullif", "greatest", "least",
    "coalesce", "round", "trunc", "abs", "ceil", "floor", "lower", "upper", "initcap",
    "length", "lpad", "rpad", "string_agg", "array_agg", "percentile_cont", "percentile_disc",
    "stddev", "variance", "rank", "dense_rank", "row_number", "ntile", "lag", "lead",
})
# Funções com tipo próprio que revelam dados do servidor em vez do negócio.
FUNCOES_TIPADAS_PROIBIDAS = ("Current",)
FUNCOES_TIPADAS_LIBERADAS = frozenset({"CurrentDate", "CurrentTimestamp"})


class SqlInseguro(Exception):
    """Exceção levantada quando uma consulta SQL não passa pela validação."""
    pass


def validar(sql: str) -> str:
    """Valida uma consulta SQL e devolve sua versão normalizada."""

    # Converte o texto SQL em uma lista de árvores sintáticas, uma por comando.
    try:
        comandos = [c for c in sqlglot.parse(sql, dialect="postgres") if c is not None]
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

    _validar_funcoes(arvore_sql)

    # Gera novamente o SQL a partir da árvore, em formato PostgreSQL normalizado e com LIMIT.
    return _limitar_linhas(arvore_sql).sql(dialect="postgres")


def _validar_funcoes(arvore_sql: exp.Expression) -> None:
    for funcao in arvore_sql.find_all(exp.Func):
        if isinstance(funcao, exp.Anonymous) and funcao.name.lower() not in FUNCOES_ANONIMAS_PERMITIDAS:
            raise SqlInseguro(f"Função não autorizada: {funcao.name}")
        tipo = type(funcao).__name__
        if tipo.startswith(FUNCOES_TIPADAS_PROIBIDAS) and tipo not in FUNCOES_TIPADAS_LIBERADAS:
            raise SqlInseguro(f"Função não autorizada: {funcao.sql(dialect='postgres')}")


def _limitar_linhas(arvore_sql: exp.Select) -> exp.Select:
    """Garante LIMIT <= LIMITE_LINHAS: o resultado vai inteiro para o contexto da LLM.

    Sem isso, "mostre todas as vendas" trazia ~30 mil linhas e estourava a cota do Gemini (429).
    """
    limite = arvore_sql.args.get("limit")
    valor = limite.expression if limite is not None else None
    if isinstance(valor, exp.Literal) and valor.is_int and int(valor.this) <= LIMITE_LINHAS:
        return arvore_sql
    return arvore_sql.limit(LIMITE_LINHAS)