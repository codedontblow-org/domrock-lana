# Text-to-SQL Query Tool
```bash
# Rodar todos os testes da ferramenta
pytest tests/tools/query_tool/ -v
```

## Visão Geral
Esta ferramenta permite que agentes de IA consultem o banco de dados relacional (PostgreSQL) usando linguagem natural. A arquitetura garante que a intenção do usuário seja traduzida em SQL, rigidamente validada contra injeções ou comandos destrutivos, executada no banco e devolvida como dados estruturados.

## Fluxo de Execução
O ciclo de vida de uma requisição segue 4 etapas rigorosas:
1. **Geração (LLM):** O modelo recebe a pergunta do usuário enriquecida com o *System Prompt*, o *Schema do Banco* e a *Data Atual*. Ele traduz a intenção para SQL ou recusa a resposta.
2. **Validação Sintática (Guard):** O SQL bruto não vai para o banco. Ele é interceptado pelo `guard.py` e analisado via Árvore Sintática Abstrata (AST) pelo `sqlglot`.
3. **Execução Segura:** A query normalizada e limitada é executada no banco de dados.
4. **Retorno ou Feedback:** Os dados são retornados ao agente. Em caso de erro na execução, o erro original do banco é devolvido para autocorreção.

*(Veja o diagrama visual em [execution-flow.md](execution-flow.md))*

## Segurança e Guardrails (`guard.py`)
A ferramenta implementa proteção no nível do código (Application Layer) para garantir consultas seguras:
* **Bloqueio DML/DDL:** Qualquer comando de escrita ou alteração estrutural (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) detectado na AST bloqueia a consulta.
* **Isolamento de Tabelas:** A query só pode fazer referência a tabelas pertencentes a um *allowlist* explícito (`marca`, `cargo`, `funcionario`, `loja`, etc.).
* **Sanitização de Funções:** Apenas funções de agregação, tratamento de strings e datas pré-aprovadas são permitidas. Funções que expõem o servidor (`pg_read_file`, `pg_sleep`) são barradas.
* **Single Statement:** Múltiplos comandos separados por ponto e vírgula são rejeitados.
* **Limitação de Linhas:** Um `LIMIT 50` é embutido na AST via código, protegendo a janela de contexto da LLM e a memória da aplicação.

## Especificação para o Agente (Tool Spec)
O agente interage com a ferramenta enviando um JSON com a pergunta e recebe um objeto com o `status` da operação. O comportamento autônomo do agente depende de interpretar os status abaixo:

### Objeto de Resposta (`QueryResponseBody`)

| Status | Significado | Ação Esperada do Agente |
| :--- | :--- | :--- |
| `sucesso` | Query validada e executada corretamente. | Utilizar o array de `dados` para formular a resposta. |
| `recusado` | LLM determinou que o schema não possui os dados. | Informar ao usuário o `motivo` da recusa. |
| `bloqueado` | O Guard barrou a query por segurança. | Ler o erro, corrigir a abordagem e tentar de novo. |
| `erro_execucao`| Falha no SGBD (ex: coluna não encontrada). | Ler o erro do banco, analisar o schema, corrigir a query e tentar novamente. |
| `erro_geracao` | Falha de comunicação com a LLM. | Pedir desculpas e sugerir tentar novamente. |

### Exemplo de Payload (Sucesso)
```json
{
  "status": "sucesso",
  "mensagem": "Consulta executada com sucesso. Resultado limitado a 50 linhas; pode haver mais dados.",
  "sql_gerado": "SELECT vlr_venda FROM venda WHERE funcionario_id = 1 LIMIT 50",
  "dados": [ {"vlr_venda": 150.50} ],
  "motivo": null,
  "erro": null
}