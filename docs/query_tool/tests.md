# Tests

```bash
# Rodar todos os testes da ferramenta
pytest tests/tools/query_tool/ -v
```

### 1. test_guard.py (Segurança e AST - 11 testes)
- Testa exclusivamente o uso do sqlglot para análise da Árvore Sintática.
- Bloqueio de Funções Nativas: Garante que tentativas de ler o SO (pg_read_file), pausar o banco (pg_sleep) ou acessar configs (current_setting) levantem a exceção SqlInseguro.
- Bloqueio de Tabelas de Sistema: Impede consultas à information_schema ou tabelas fora do allowlist (ex: usuario).
- Bloqueio de Destruição (DML/DDL): Barra comandos DELETE, DROP e injeções acopladas via ponto-e-vírgula (ex: SELECT 1; DROP TABLE).
- Mutação Segura: Confirma que a query final recebe o LIMIT 50 via código e aceita agregações complexas de data (ex: to_char, CURRENT_DATE).

### 2. test_service.py (Lógica de Negócio e Feedbacks - 4 testes)
- Usa unittest.mock.patch para simular as respostas da LLM e do Banco, focando na resiliência do sistema.
- Sucesso: Confirma que uma requisição limpa retorna sucesso com os dados corretos.
- Autocorreção (Self-Healing): Testa se, ao ocorrer um Exception do SGBD, o texto do erro real do PostgreSQL é capturado e retornado no status erro_execucao para o agente conseguir consertar.
- Bloqueio do Guard: Garante que a exceção de segurança vire o status bloqueado.
- Recusa da LLM: Confirma que uma query devolvida como SEM_DADO resulte no status recusado.

### 3. test_tool.py (Interface do LangChain - 1 teste)
- Garante que a "casca" da Tool instanciada com @tool esteja corretamente roteando os argumentos para o service.executar sem perdas no payload.