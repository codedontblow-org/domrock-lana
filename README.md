# Camplana - Lana

Servidor para hospedar **Lana**, o agente AI do projeto CamplanaAI. Utiliza **FastAPI** para endpoints REST/HTTP, **gRPC** para comunicação de alta performance com o backend Spring Boot, e **LangGraph** para gerenciar os fluxos do agente.

## 📂 Estrutura do Projeto

```text
domrock-lana/
├── app/
│   ├── agent/                  # Lógica do LangGraph e Agent Workflows
│   │   ├── graph.py            # Construção do Grafo de Estados do LangGraph
│   │   ├── initialize.py       # Inicialização das ferramentas e estado
│   │   ├── prompts.py          # Prompts do sistema (SYSTEM_RULES)
│   │   ├── service.py          # Serviço de invocação do agente (lana_invoke)
│   │   └── supervisor.py       # Nó Router / Supervisor (decisão de rotas)
│   ├── core/
│   │   └── config.py           # Configurações de API Keys e variáveis de ambiente
│   ├── proto/                  # Arquivos compilados do Protobuf (gRPC)
│   │   ├── ia_service_pb2.py
│   │   └── ia_service_pb2_grpc.py
│   ├── schemas/                # DTOs de entrada/saída HTTP (Pydantic)
│   ├── tools/                  # Definição e Pydantic Schemas das Tools
│   │   ├── query_tool.py       # Chamadas HTTP para os endpoints da API Java
│   │   ├── code_tool.py        # Gerador, parser (AST) e executor do código Python
│   │   └── slot_fill.py        # Ferramenta para comunicação fácil com usuário
│   └── grpc_server.py          # Servidor gRPC (roda na porta 50051)
├── main.py                     # Ponto de entrada FastAPI e inicializador do gRPC
├── requirements.txt
├── env.example
└── README.md
```

## Requisitos

- python3.12.10

## Executando

Clone o repositório, acesse a raiz e rode os seguinte comandos:

> Tenha certeza que está usando a versão 3.12 do python para evitar problemas com dependências

```bash
# Windows (CMD)
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS (Bash)
python3.12 -m venv venv
source venv/bin/activate

# Instalar dependências
python -m pip install -r requirements.txt

# Subir a aplicação (FastAPI + gRPC)
uvicorn main:app --reload

```

### Portas Ativas:

HTTP/REST (Swagger): http://localhost:8000/docs

Serviço gRPC: localhost:50051 (utilizado pelo Spring Boot)

---

## Licença

Este projeto está sob a licença especificada no arquivo [LICENSE](LICENSE).
