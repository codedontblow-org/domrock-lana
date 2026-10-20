# Camplana - Lana

A Lana é o agente de IA do Camplana. Ela conversa com o gestor em português, consulta a base de vendas (só leitura), monta a ficha da campanha e simula quanto a campanha custa em comissão.

Nenhum número da simulação vem da LLM: a IA gera o código da regra, o código roda isolado e o resultado é conferido com um cálculo determinístico. Quem chama a Lana é o backend (Spring), nunca o front.

## 🧭 Onde a Lana fica no sistema

```text
Front (Vue) ──► Backend (Spring) ──► Lana ──► PostgreSQL (papel lana_leitura, só SELECT)
                                      │
                                      └─────► Provedor de IA (Gemini, OpenRouter ou Groq)
```

A Lana atende em duas portas:

| Porta | Protocolo | Rota | Para quê |
| --- | --- | --- | --- |
| 50051 | gRPC | `IAService.InvokeAgent` ([`app/proto/ia_service.proto`](app/proto/ia_service.proto)) | Chat. É por aqui que o backend conversa com a Lana |
| 8000 | HTTP | `POST /agent/invoke` | Chat (mesmo agente). Além do texto, devolve `events` (ferramentas usadas) e `regra` (ficha da campanha) |
| 8000 | HTTP | `POST /simulacao` | Simula a campanha a partir da ficha (`regra`) |
| 8000 | HTTP | `GET /` | Diz se a Lana está no ar |
| 8000 | HTTP | `/docs` | Swagger, com os formatos de requisição e resposta |

Erros que o backend precisa tratar:

| Onde | Resposta | Quando |
| --- | --- | --- |
| `POST /agent/invoke` | 503 `{"etapa": "cota_llm", "mensagem": ...}` | O provedor de IA recusou por cota (429) |
| `POST /simulacao` | 422 `{"etapa": ..., "mensagem": ...}` | Ficha incompleta (`validacao`), mês sem base importada (`dados`), código gerado que falhou nas duas tentativas (`geracao_codigo`) ou erro na comissão atual (`baseline`) |
| gRPC | `RESOURCE_EXHAUSTED` | Cota do provedor de IA |
| gRPC | `DEADLINE_EXCEEDED` | A Lana passou de 100 s |
| gRPC | `INTERNAL` | Qualquer outro erro do agente |

## 📂 Estrutura do Projeto

```text
domrock-lana/
├── main.py                  # FastAPI (rotas HTTP); sobe o servidor gRPC junto (lifespan)
├── app/
│   ├── grpc_server.py       # Servidor gRPC na porta 50051
│   ├── proto/               # ia_service.proto e o código gerado a partir dele (*_pb2*.py)
│   ├── core/
│   │   ├── config.py        # Variáveis de ambiente e cadeia de modelos com reserva (fallback)
│   │   └── db.py            # Conexão só leitura com o PostgreSQL (timeout de 15 s)
│   ├── agent/               # O agente (LangGraph)
│   │   ├── graph.py         # Grafo agente ⇄ ferramentas; histórico da conversa em memória
│   │   ├── initialize.py    # Estado, ferramentas e modelo do agente
│   │   ├── supervisor.py    # Nó do agente e decisão de chamar ferramenta ou responder
│   │   ├── prompts.py       # Regras do agente: escopo, tom, sigilo
│   │   ├── service.py       # lana_invoke: um turno da conversa (texto, events, regra)
│   │   ├── router.py        # POST /agent/invoke
│   │   ├── ia_servicer.py   # InvokeAgent (gRPC)
│   │   ├── guardrails.py    # Respostas prontas para saudação e ajuda, sem gastar a LLM
│   │   └── cli-invoke.py    # Conversa pelo terminal, para teste manual
│   ├── tools/               # Ferramentas que o agente pode chamar
│   │   ├── query_tool/      # consultar_banco: pergunta → SQL validado → SELECT
│   │   ├── regra_tool/      # registrar_parametros_regra: monta a ficha da campanha
│   │   └── code_tool/       # Gera, valida e executa o código da regra
│   └── simulacao/           # POST /simulacao: bases, comissão atual, cenários, resumo e explicação
├── tests/                   # pytest; usam fakes, não chamam a LLM nem o banco
├── docs/query_tool/         # Documentação da consultar_banco
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt     # requirements.txt + pytest
└── .env.example
```

## ⚙️ Tecnologias Utilizadas

- Python 3.12 (CI e Docker usam 3.12.14; o 3.13 também funciona localmente)
- FastAPI + Uvicorn (HTTP) e grpcio (gRPC)
- LangGraph / LangChain, com Gemini, OpenRouter e Groq
- psycopg2 (PostgreSQL), sqlglot (validação do SQL), rapidfuzz (guardrails)
- pytest

## 🔑 Variáveis de ambiente

A Lana lê o arquivo `.env` na raiz deste repositório (modelo em [`.env.example`](.env.example)). Variáveis do ambiente também valem e têm prioridade.

| Variável | Obrigatória | Padrão | O que é |
| --- | --- | --- | --- |
| `AI_PROVIDER` | sim | | Provedor principal: `GEMINI`, `OPENROUTER` ou `GROQ` |
| `AI_MODEL` | sim | | Modelo principal, no nome do provedor (ex.: `gemini-3.5-flash-lite`) |
| `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY` | a do provedor principal | | Provedor sem chave fica fora da cadeia |
| `AI_FALLBACKS` | não | vazio | Reservas em ordem, se o principal falhar: `PROVEDOR:modelo,PROVEDOR:modelo` |
| `AI_TIMEOUT_S` | não | `30` | Segundos por modelo antes de passar ao próximo da cadeia |
| `DATABASE_URL` | para chat com dados e simulação | | Banco do backend com o papel `lana_leitura` (criado pela migração V3 do backend) |
| `CODEGEN_MODO` | não | `llm` | `llm`: a IA gera o código e ele é conferido; `modelo`: usa só o cálculo fixo (plano B) |

As portas não vêm do `.env`: a HTTP é a do comando `uvicorn` (`--port`) e a gRPC é fixa em 50051 (`app/grpc_server.py`).

## ❓ Como Executar

### Pré-requisitos

- Python 3.12 (ou 3.13)
- O PostgreSQL do backend no ar, com as migrações aplicadas. Quem cria as tabelas e o papel `lana_leitura` é o backend, ao subir pela primeira vez (veja o [README do backend](https://github.com/codedontblow-org/domrock-backend)).
- Uma chave de API de pelo menos um provedor de IA
- As portas 8000 e 50051 livres

### Passo a passo

```bash
# 1. Ambiente virtual (só na primeira vez)
python3 -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 2. Configuração
cp .env.example .env
# Preencha AI_PROVIDER, AI_MODEL, a chave do provedor e o DATABASE_URL.
# Se o banco do backend estiver em outra porta (ex.: 5433), ajuste o DATABASE_URL.

# 3. Subir (HTTP na 8000 e gRPC na 50051)
uvicorn main:app --port 8000
```

Use `--reload` no comando do `uvicorn` para reiniciar sozinho a cada mudança no código.

### Conferir se subiu

```bash
curl http://localhost:8000/
# {"status":"lana-ai is running","grpc":"active on port 50051"}

curl -X POST http://localhost:8000/agent/invoke \
  -H 'Content-Type: application/json' \
  -d '{"chat_id": "teste-1", "message": "Quanto a marca 30 vendeu em outubro de 2025?"}'
# Com o dataset completo, a resposta traz R$ 333.666,01.
```

O Swagger fica em http://localhost:8000/docs. Para conversar com o agente pelo terminal, sem subir o servidor: `PYTHONPATH=. python app/agent/cli-invoke.py` (`!q` sai da conversa).

### Com Docker

```bash
docker build -t camplana-lana .
docker run --rm --env-file .env \
  -e DATABASE_URL=postgresql://lana_leitura:lana_leitura@host.docker.internal:5432/camplana \
  --add-host=host.docker.internal:host-gateway \
  -p 8000:8000 -p 50051:50051 camplana-lana
```

Dentro do container, `localhost` é o próprio container: por isso o `DATABASE_URL` aponta para `host.docker.internal`.

### Sistema completo

Para subir banco, backend, Lana e front de uma vez, use o [repositório principal](https://github.com/codedontblow-org/domrock-camplana).

## 🧪 Testes

```bash
pip install -r requirements-dev.txt
AI_PROVIDER=GEMINI AI_MODEL=modelo-de-teste GEMINI_API_KEY=chave-de-teste python -m pytest -q
```

- Os testes usam fakes (`tests/fakes.py`): não chamam a LLM nem o banco. Mesmo assim, `app/core/config.py` exige `AI_PROVIDER`, `AI_MODEL` e uma chave ao ser importado; valores fictícios bastam (ou o seu `.env`).
- O teste do executor real do código gerado usa limites de recursos do Linux; no Windows, rode pelo WSL ou pelo Docker.
- O CI (`.github/workflows/ci.yml`) roda os testes e o build da imagem Docker a cada push e PR para `main` e `develop`.

## 🛡️ Segurança

- **Banco:** a Lana entra com o papel `lana_leitura` (só SELECT), em sessão só leitura e com timeout de 15 s. O SQL que a IA escreve passa pelo `sqlglot` antes de ir ao banco: só SELECT, só funções permitidas e no máximo 50 linhas. Detalhes em [`docs/query_tool/README.md`](docs/query_tool/README.md).
- **Código gerado:** antes de rodar, é validado pela árvore sintática: só importa `pandas`, `numpy`, `math` e `datetime`, sem funções e atributos perigosos. Roda em outro processo (`python -I -B`), com ambiente vazio, tempo de CPU e memória limitados e sem poder gravar arquivos.
- **Números:** com `CODEGEN_MODO=llm`, o resultado do código da IA é comparado com o cálculo determinístico. Se divergir, a IA tenta de novo com a dica. Se divergir outra vez, vale o cálculo determinístico, e o resultado avisa em `observacao`.
- **Dados na LLM:** na simulação, as bases não passam pela LLM. Ela só gera o código e escreve a explicação a partir de um resumo.
- **Guardrails:** no gRPC, saudação e pedido de ajuda são respondidos com texto pronto, sem chamar a LLM.

## 🔄 Mudar o contrato gRPC

O `ia_service.proto` existe nos dois repositórios e precisa ser igual nos dois:

- Lana: `app/proto/ia_service.proto`
- Backend: `src/main/proto/ia_service.proto`

Depois de editar o `.proto` aqui, gere o código Python de novo (na raiz deste repositório, com o venv ativo):

```bash
python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. app/proto/ia_service.proto
```

Depois, copie o `.proto` para o backend; o build do backend gera o código Java.

## ⚠️ Limitações conhecidas

- O histórico da conversa fica só na memória da Lana (`InMemorySaver`, por `chat_id`): reiniciar a Lana apaga as conversas.
- Pelo gRPC, a resposta leva só o texto. Os campos `regra_json` e `events_json` existem no `.proto`, mas ainda não são preenchidos, e a ficha enviada pelo backend é ignorada. Pelo HTTP `/agent/invoke`, a ficha e os eventos vêm completos.
- Os guardrails só valem no gRPC; o `/agent/invoke` sempre chama a LLM.
- A comissão atual (baseline) aplica só as regras gerais da especificação (5a e 5b): ainda sem proporcional de admissão e demissão, férias e afastamentos.
