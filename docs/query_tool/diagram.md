## Diagrama

```mermaid
graph TD
    A[Agente de IA] -->|1. Pergunta em Linguagem Natural| B(LLM - service.gerar_sql)
    
    B -->|2. Identifica ausência no Schema| C[Recusado: Informa o Agente]
    B -->|3. Gera SQL| D{Guard de Segurança - guard.validar}
    
    D -->|4. Detecta Injeção ou DDL/DML| E[Bloqueado: Retorna Erro ao Agente]
    D -->|5. SQL Seguro aprovado via AST| F[(Banco de Dados PostgreSQL)]
    
    F -->|6. Falha de Sintaxe/Coluna Inexistente| G[Erro DB: Retorna pista ao Agente]
    F -->|7. Execução com Sucesso| H[Retorna Dados + Limit 50 aplicados]
    
    H --> A
    C --> A
    
    %% Loop de autocorreção
    E -.->|Agente lê o motivo do bloqueio e refatora| A
    G -.->|Agente lê o erro do PostgreSQL e corrige a query| A