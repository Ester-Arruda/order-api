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
