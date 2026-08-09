# ADR 002 — Usar DBaaS PostgreSQL da Magalu Cloud

**Status:** Aceito
**Data:** 2026-08-04

## Contexto
A aplicação precisa de persistência de dados. O banco precisa sobreviver
a reinicializações de containers e estar disponível para múltiplas réplicas
da API simultaneamente.

## Alternativas consideradas
- **DBaaS PostgreSQL gerenciado (externo)** — backup, patch e HA pelo provedor; custo maior; menos controle fino.
- **PostgreSQL em pod com PVC** — custo baixo, tudo em um lugar; volume, backup e recuperação por nossa conta; o dado morre junto com o cluster.

## Decisão
Usar o serviço DBaaS PostgreSQL da Magalu Cloud — banco gerenciado,
sem necessidade de operar o servidor de banco de dados. Critério: disponibilidade e custo de operação (estado é caro de operar manualmente).

## Consequências
**Positivas:**
- Backup automático gerenciado pelo provedor
- Sem custo operacional de administração do banco
- Conexões simultâneas de múltiplos pods sem conflito
- Alta disponibilidade incluída no serviço

**Negativas:**
- Custo por hora de uso, mesmo com pouco tráfego
- Menor controle sobre configurações avançadas do PostgreSQL
- Dependência do provedor para upgrades de versão
