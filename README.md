# API de Pedidos

API REST para gestão de pedidos e itens, construída em **Python** com **FastAPI**.

> Projeto base do curso **Move Tech — Magalu × Prósper Digital Skills**.

![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.11x-009688)
![Docker](https://img.shields.io/badge/docker-ready-2496ED)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Sumário

- [Sobre](#sobre)
- [Stack](#stack)
- [Pré-requisitos](#pré-requisitos)
- [Como rodar](#como-rodar)
  - [Com Docker](#com-docker)
  - [Localmente (sem Docker)](#localmente-sem-docker)
- [Observabilidade](#observabilidade)
- [Endpoints da API](#endpoints-da-api)
- [Exemplos de uso](#exemplos-de-uso)
- [Testes](#testes)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Licença](#licença)

---

## Sobre

Serviço que expõe operações de criação, consulta e cancelamento de pedidos, além do gerenciamento de itens associados a cada pedido. Inclui métricas Prometheus e documentação interativa via Scalar.

## Stack

- **Linguagem:** Python 3.11
- **Framework:** FastAPI
- **ORM:** SQLAlchemy
- **Documentação interativa:** Scalar (`scalar_fastapi`)
- **Métricas:** Prometheus (`prometheus_fastapi_instrumentator`)
- **Containerização:** Docker / Docker Compose
- **Deploy:** Kubernetes (manifests em `k8s/`)

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) ou [Docker Engine](https://docs.docker.com/engine/install/) (Linux)
- Para rodar sem Docker: Python 3.11+ e [Poetry](https://python-poetry.org/docs/#installation)

## Como rodar

### Com Docker

```bash
docker compose up --build
```

A API estará disponível em `http://localhost:8000`.

### Localmente (sem Docker)

```bash
poetry install
poetry run uvicorn app.main:app --reload
```

## Observabilidade

- **Documentação interativa:** `http://localhost:8000/docs` (via Scalar)
- **Métricas Prometheus:** `http://localhost:8000/metrics`
- **Health check:** `GET /health` — retorna o status da aplicação e da conexão com o banco de dados

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Verifica se a API e o banco de dados estão no ar |
| `GET` | `/stats` | Retorna estatísticas de pedidos e itens |
| `POST` | `/orders` | Cria um novo pedido |
| `GET` | `/orders` | Lista todos os pedidos |
| `GET` | `/orders/{id}` | Retorna um pedido com seus itens |
| `DELETE` | `/orders/{id}` | Cancela um pedido (soft delete, status `cancelled`) |
| `POST` | `/orders/{id}/items` | Adiciona um item ao pedido |
| `GET` | `/orders/{id}/items` | Lista os itens de um pedido |

## Exemplos de uso

### Criar um pedido

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "Maria Silva"
  }'
```

**Resposta (`201 Created`):**

```json
{
  "id": "b3f1c2e4-1a2b-4c3d-9e8f-1234567890ab",
  "customer": "Maria Silva",
  "status": "open",
  "created_at": "2026-08-07T10:00:00",
  "items": []
}
```

### Adicionar um item ao pedido

```bash
curl -X POST http://localhost:8000/orders/{order_id}/items \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "CAM-PRETA-M",
    "description": "Camiseta Preta - Tamanho M",
    "quantity": 2
  }'
```

**Resposta (`201 Created`):**

```json
{
  "id": "d4e5f6a7-2b3c-4d5e-8f9a-0987654321cd",
  "sku": "CAM-PRETA-M",
  "description": "Camiseta Preta - Tamanho M",
  "quantity": 2
}
```

### Cancelar um pedido

```bash
curl -X DELETE http://localhost:8000/orders/{order_id}
```

**Resposta:** `204 No Content`

### Estatísticas

```bash
curl http://localhost:8000/stats
```

**Resposta:**

```json
{
  "orders": {
    "total": 12,
    "open": 9,
    "cancelled": 3
  },
  "items": {
    "total": 27
  }
}
```

## Testes

```bash
poetry run pytest
```

## Estrutura do projeto

```
.
├── .github/
│   └── workflows/
│       └── deploy.yml
├── app/
│   ├── database.py
│   ├── main.py
│   └── models.py
├── docs/
│   └── data-model.md
├── k8s/
│   └── app.yaml
├── tests/
│   └── test_main.py
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```
