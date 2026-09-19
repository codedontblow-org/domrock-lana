# Camplana - Lana
Servidor simples para hospedar Lana, o agente AI do projeto CamplanaAI! Utiliza FastAPI para hospedagem e LangGraph para gerenciar o agente.

## 📂 Estrutura do Projeto
```text
lana-ai/ 
├── app/ 
│   ├── main.py                 # Ponto de entrada da API FastAPI (rotas chamadas pelo SpringBoot) 
│   ├── core/ 
│   │   └── config.py           # Configurações de API Keys (Gemini) e variáveis de ambiente 
│   ├── agent/                  # Lógica do LangGraph
│   │   ├── state.py            # Definição da classe de Estado (AgentState) 
│   │   ├── supervisor.py       # Nó Router / Supervisor (deliberação e decisão de rotas) 
│   │   └── graph.py            # Construção do Grafo de Estados do LangGraph 
│   ├── tools/                  # Definição e Pydantic Schemas das Tools 
│   │   ├── query_tool.py      # Chamadas HTTP para os endpoints da API Java 
│   │   ├── code_tool.py       # Gerador, parser (AST) e executor do código Python 
│   │   └── slot_fill.py        # Ferramenta para comunicação fácil com usuário
│   └── schemas/                # DTOs de entrada/saída HTTP (Pydantic) 
├── requirements.txt
├── env.example
└── README.md
```

## Requisitos
- python3.12


## Executando
Clone o repositório, acesse a raiz e rode os seguinte comandos:
> Tenha certeza que está usando a versão 3.12 do python para evitar problemas com dependências

```bash
# cmd
python -m venv venv
.\venv\Scripts\activate 

# bash
python3.12 -m venv venv  
source venv/bin/activate 

python -m pip install -r requirements.txt

# localhost:8000
uvicorn main:app --reload  

# acessar Swagger UI
http://localhost:8000/docs

```