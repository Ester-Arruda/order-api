# ADR 001 — Usar K3s para deploy da aplicação

**Status:** Aceito
**Data:** 2026-08-04

## Contexto
A aplicação precisa ser implantada na Magalu Cloud de forma acessível
publicamente, resiliente a falhas e com capacidade de escalar.

## Alternativas consideradas

- **K3s em VM** — Kubernetes leve; cobra só a VM; provisionamento < 2 min; sem HA nativa.
- **MKS (Kubernetes Gerenciado)** — control plane e HA gerenciados; custo maior; provisionamento 5-10 min.
- **VM com Docker Compose** — mais simples de subir; sem orquestração, self-healing nem escala declarativa.
- **VM com Nomad** — orquestrador mais leve que Kubernetes; descartado por não reaproveitar
  o conhecimento de manifests Kubernetes que o time já tem, e por ter ecossistema de
  observabilidade (Prometheus, probes) menos padronizado que o de K8s.
- **Serverless / Functions as a Service** — descartado porque a aplicação é um serviço HTTP
  com estado de conexão persistente ao banco (SQLAlchemy `Session` por request) e não um
  conjunto de funções orientadas a evento; o modelo de cold start e timeout de FaaS não se
  encaixa no perfil de uso atual.

### Comparativo

| | K3s em VM | MKS | VM + Docker Compose |
|---|---|---|---|
| Custo | Só a VM | VM + taxa de control plane | Só a VM |
| Provisionamento | < 2 min (script `k3s-mgc`) | 5-10 min | < 1 min |
| HA nativa | Não | Sim (control plane gerenciado) | Não |
| Self-healing de pod | Sim (liveness probe) | Sim | Não (precisa de `restart: always` manual) |
| Escala declarativa (réplicas) | Sim | Sim | Não (precisa subir serviço por serviço) |
| Lock-in | Nenhum (manifests padrão) | Nenhum (manifests padrão) | Alto (compose não migra direto pra K8s) |
| Curva de aprendizado | Kubernetes básico | Kubernetes básico | Baixa |

## Decisão

Usar K3s em uma VM BV2-2-40 (Ubuntu 24.04) com Klipper ServiceLB
para expor a aplicação na porta 80 do IP público da VM.
O script `k3s-mgc` automatiza todo o provisionamento. Critério: menor custo e provisionamento mais rápido, com manifests idênticos a qualquer Kubernetes.

## Consequências

**Positivas:**
- Custo menor que o MKS (cobra apenas pela VM e não pelo control plane)
- Provisionamento em menos de 2 minutos
- Manifests YAML idênticos a qualquer Kubernetes padrão (sem lock-in)
- Restart automático em caso de falha (liveness probe)
- Escalabilidade horizontal simples (basta aumentar o número de réplicas)

**Negativas:**
- Single point of failure: sem alta disponibilidade nativa (tudo em uma VM)
- Armazenamento efêmero: volumes locais desaparecem se a VM for recriada
- Sem auto-scaling de nós: capacidade fixa (2 vCPU, 2 GB)
- IP público muda se a VM for substituída

### Mitigação dos riscos aceitos

Nenhuma decisão abaixo elimina os riscos listados acima — só reduz o impacto
enquanto a topologia single-node for mantida:

| Risco | Mitigação atual | Mitigação futura (se necessário) |
|---|---|---|
| SPOF da VM | 2 réplicas de pod reduzem impacto de falha de *pod*, não de *nó* | Migrar para K3s multi-node ou MKS (ver gatilhos abaixo) |
| Armazenamento efêmero | Aplicação é stateless — todo o estado persiste no DBaaS externo, não em volume local | N/A (efêmero é aceitável enquanto nada crítico for salvo em disco local) |
| Capacidade fixa (2 vCPU/2 GB) | Monitorar `kubectl top nodes` e o teste de carga k6 (ver `docs/architecture.md`) para saber quando a VM satura | Redimensionar a VM (`machine_type` maior) antes de considerar HPA com `maxReplicas` alto |
| IP público muda ao recriar VM | Nenhuma hoje | Reservar IP fixo/elastic IP da MGC, ou colocar um domínio com TTL baixo apontando pro IP atual |

### Gatilhos para revisar esta decisão

Esta decisão deve ser reaberta quando qualquer um destes ocorrer:

- A meta de disponibilidade do produto subir acima do que uma VM single-node
  consegue sustentar (hoje 99,5% mensal, ver `docs/architecture.md`).
- Um incidente real de indisponibilidade for causado por falha da VM (não de pod) —
  sinal de que o risco aceito aqui já está custando caro na prática.
- O time crescer e passar a ter capacidade de operar um cluster multi-node.
- Um segundo serviço (ex.: `notification-service`, ver `docs/architecture.md`) precisar
  compartilhar o cluster, aumentando a criticidade de HA do control plane.

Quando algum gatilho ocorrer, as opções a reavaliar são, em ordem crescente de esforço:
K3s multi-node (mesmos manifests, kubeconfig aponta pra mais nós) → migração para MKS
(control plane gerenciado, mesmos manifests).

## Referências

- Script de provisionamento: `k3s-mgc`
- Documentação Magalu Cloud: https://docs.magalu.cloud/
- Documentação K3s: https://docs.k3s.io/
