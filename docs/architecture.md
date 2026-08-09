# Arquitetura da solução

```mermaid
flowchart TB
    Cliente(["Cliente / Usuário"])

    subgraph GH["GitHub"]
        Repo["Repositório\n(order-api)"]
        Actions["GitHub Actions\n(CI/CD)"]
    end

    subgraph MGC["Magalu Cloud · região br-se1"]
        Registry["Container Registry\narmazena versões da aplicação"]
        DB[("DBaaS PostgreSQL\npersiste pedidos e itens")]

        subgraph VM["VM BV2-2-40 · K3s (single node)"]
            LB["Klipper ServiceLB\nIP da VM, porta 80"]
            Pod1["API — réplica 1"]
            Pod2["API — réplica 2"]
        end
    end

    Repo -- "push / workflow_dispatch" --> Actions
    Actions -- "docker build + push\n(HTTPS, Registry API)" --> Registry
    Actions -- "kubectl apply\n(HTTPS, Kubernetes API)" --> VM
    Actions -- "kubectl create secret\n(HTTPS, Kubernetes API) — injeta DATABASE_URL" --> VM

    Cliente -- "HTTP, porta 80" --> LB
    LB -- "distribui requisições HTTP" --> Pod1
    LB -- "distribui requisições HTTP" --> Pod2

    VM -- "docker pull\n(HTTPS, Registry API)" --> Registry

    Pod1 -- "SQL, TCP 5432 (psycopg2)" --> DB
    Pod2 -- "SQL, TCP 5432 (psycopg2)" --> DB
```

## Componentes

| Componente | Serviço MGC | Função |
|---|---|---|
| API | K3s (VM single node) — 2 réplicas | Processa as requisições HTTP |
| Banco de dados | DBaaS PostgreSQL | Persiste pedidos e itens |
| Imagens | Container Registry | Armazena versões da aplicação |
| Tráfego externo | Klipper ServiceLB (IP da VM, porta 80) | Distribui entre as réplicas e fornece acesso externo |
| CI/CD | GitHub Actions | Automatiza testes, build e deploy |


### Camadas internas da API

Cada réplica roda a mesma imagem, com o código organizado em quatro camadas dentro do processo Python:

| Camada | Pasta | Responsabilidade |
|---|---|---|
| API | `app/api/v1/` | Recebe a requisição HTTP, valida entrada (Pydantic) e traduz o retorno do service em status code / exceção |
| Service | `app/services/` | Regra de negócio, orquestra o repository e monta a resposta |
| Repository | `app/repositories/` | Único ponto que fala com o PostgreSQL via SQLAlchemy (queries, commit, refresh) |
| Model | `app/models/` | Entidades ORM (`Order`, `Item`) |

Essa separação existe para isolar a regra de negócio do detalhe de transporte (HTTP) e do detalhe de persistência (SQLAlchemy) — trocar o ORM ou adicionar um segundo transporte (ex.: um worker consumindo fila) não deveria exigir tocar em `app/api`.

## Fluxo

1. **Deploy**: um push (ou disparo manual) no GitHub aciona o GitHub Actions, que roda os testes, builda a imagem, faz `docker push` para o Container Registry e aplica os manifestos no cluster via `kubectl apply` (usando o kubeconfig da VM K3s). A `DATABASE_URL` é injetada como Secret do Kubernetes nesse mesmo passo, nunca commitada no repositório.
2. **Runtime**: o K3s na VM puxa a imagem do Container Registry e sobe as 2 réplicas da API. O Klipper ServiceLB expõe a porta 80 no IP da própria VM e distribui as requisições entre as réplicas.
3. **Persistência**: cada réplica da API conecta diretamente ao DBaaS PostgreSQL (serviço gerenciado da MGC, externo à VM) via SQL/TCP na porta 5432, passando pela camada `repositories`.

## Requisitos não-funcionais

Números, não adjetivos. Todos mensuráveis a partir do `/metrics` (exposto pelo
`prometheus-fastapi-instrumentator`) e do Klipper ServiceLB/probes do K8s.

| Requisito | Como medir | Alvo |
|---|---|---|
| Disponibilidade | Erros 5xx e uptime das probes (`livenessProbe`/`readinessProbe` em `/health`) no Grafana | 99,5% mensal (≈ 3h39min de indisponibilidade/mês) |
| Latência | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` do `/metrics` | P95 < 500 ms |
| Escalabilidade | Teste de carga (k6) + `rate(http_requests_total[1m])` | 300 req/s sem degradar (P95 se mantém < 500 ms e taxa de erro 5xx < 1%) |
| Custo | VM + DBaaS + IP na calculadora MGC | Teto definido em ADR |

### Detalhamento

**Disponibilidade — 99,5% mensal**
- Medido como `1 - (minutos com probe falhando ou retornando 5xx / minutos no mês)`.
- Com 2 réplicas atrás do Klipper ServiceLB, uma falha de pod isolada não deve contar
  como indisponibilidade — só conta se **ambas** as réplicas estiverem fora ao mesmo tempo,
  ou se o `/health` reportar `database: unavailable`.
- 99,5% mensal permite ~3h39min de indisponibilidade acumulada por mês — folga suficiente
  pra rolling updates e reinícios pontuais do K3s single-node, sem exigir HA de VM (que
  esse desenho não tem: é um único nó).

**Latência — P95 < 500 ms**
- Query Prometheus: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, handler))`.
- Medido por rota (`handler`), não agregado — `POST /orders/{id}/items` e `GET /orders`
  têm perfis de latência diferentes; agregar tudo esconde regressões em uma rota específica.
- 500 ms é alvo de p95 sob carga normal, não pico; ver escalabilidade abaixo para o
  comportamento sob 300 req/s.

**Escalabilidade — 300 req/s sem degradar**
- Script k6 com ramp-up gradual até 300 req/s sustentado por pelo menos 5 minutos,
  distribuído entre os endpoints principais (`POST /orders`, `POST /orders/{id}/items`,
  `GET /orders/{id}`) na proporção esperada de uso real.
- "Sem degradar" = durante o teste, P95 continua < 500 ms **e** taxa de erro 5xx < 1%
  **e** `rate(http_requests_total[1m])` acompanha a carga gerada (sem fila crescendo,
  sinal de saturação).
- Como é VM single-node, o teto real de RPS é limitado pelo `machine_type` da VM
  (BV2-2-40) e pelo DBaaS — o k6 também deve reportar em que ponto (se houver) a
  aplicação para de acompanhar a carga, para orientar decisão de subir o tipo de
  máquina ou o plano do banco antes de precisar de fato.

**Custo — teto definido em ADR**
- Composição: VM (BV2-2-40) + DBaaS PostgreSQL (plano definido) + IP público (Klipper
  usa o IP da própria VM, sem custo adicional de LoadBalancer) + Container Registry.
- Valores tirados da calculadora oficial da MGC (https://docs.magalu.cloud/) no momento
  do dimensionamento; o teto e a justificativa de cada item ficam registrados em ADR
  separado (`docs/adr/`), não neste documento — arquitetura descreve o "o quê", o ADR
  registra o "por quê" e o valor aprovado, que muda com mais frequência que o desenho.

## Estilo arquitetural

**Atual: monolito em camadas**, implantado como container único com duas réplicas.

A aplicação é um único processo/imagem contendo quatro camadas internas — API
(`app/api`, os routers HTTP), serviço (`app/services`, regra de negócio), repositório
(`app/repositories`, acesso ao PostgreSQL) e modelo (`app/models`, entidades ORM). As
camadas são um limite *lógico* de código (cada uma só conhece a camada abaixo dela: API
não fala com repository direto, service não conhece `Session` do SQLAlchemy fora do
repository), não um limite de *implantação*: não há rede nem serialização entre elas,
tudo roda no mesmo processo Python, replicado horizontalmente (2 réplicas) atrás do
Klipper ServiceLB para disponibilidade e throughput.

Esse estilo é a escolha certa agora: um domínio só (pedidos), um time só, sem necessidade
de escalar partes da aplicação de forma independente. Monolito em camadas troca
flexibilidade de escala granular por simplicidade operacional — um único deploy, um único
banco, um único conjunto de logs/métricas — o que é exatamente o trade-off que faz sentido
no estágio atual do projeto.

**Estilo-alvo, se o domínio de notificações crescer:** extrair um segundo serviço.

O gatilho não é "crescer" em volume de requisições (isso o monolito replicado já absorve
— ver Escalabilidade acima) — é o **domínio de notificações ganhar responsabilidades
próprias** (múltiplos canais, templates, retries e filas independentes do fluxo de
pedidos, regras de negócio que não têm relação com `Order`/`Item`). Quando isso acontecer,
a extração seria:

- Um segundo serviço (`notification-service`), com seu próprio deploy, réplicas e,
  possivelmente, seu próprio banco — deixando de compartilhar o schema do `order-api`.
- Comunicação entre os dois via evento (ex.: `order_created`, `order_cancelled`)
  em vez de chamada HTTP síncrona, para o serviço de pedidos não ficar acoplado à
  disponibilidade do serviço de notificações.
- Nesse ponto o estilo muda de monolito em camadas para **arquitetura orientada a
  serviços** (não necessariamente "microsserviços" completo — dois serviços bem
  desenhados já contam) com comunicação assíncrona entre os dois domínios.

Até lá, notificações (se existirem) ficam como mais um módulo dentro do monolito atual —
extrair cedo demais troca a simplicidade de agora por complexidade operacional (dois
deploys, duas bases, mensageria) sem um domínio que justifique o custo. A própria
separação em `api/services/repositories/models` já deixa essa extração futura mais barata:
o `order_service.py` de hoje é praticamente o esboço do que viraria a API interna do
serviço de pedidos se um segundo serviço aparecer.

## Trade-offs

| Aspecto | Decisão tomada | Alternativa não escolhida | Motivo da escolha |
|---|---|---|---|
| Deploy | K3s em VM | MKS (Kubernetes Gerenciado) | Custo menor, provisionamento < 2 min, manifests idênticos |
| Topologia do cluster | K3s **single-node** | K3s multi-node (2-3 VMs) | Custo é a prioridade nesta fase; aceita-se a VM como ponto único de falha (SPOF) — ver detalhe abaixo |
| Banco | DBaaS gerenciado | PostgreSQL em container | Backup automático, sem administração |
| CI/CD | GitHub Actions | Deploy manual | Consistência e rastreabilidade |
| Réplicas | 2 pods | 1 pod | Disponibilidade mínima sem custo excessivo — mas ambas competem pelos mesmos 2 vCPU/2 GB da VM |
| API | FastAPI (Python) | Node.js, Go, Java | Curva de aprendizado baixa, alta produtividade |
| Estrutura de código | Camadas (`api`/`services`/`repositories`/`models`) | Tudo em `main.py` (script único) | Testabilidade (service e repository são testáveis sem subir HTTP) e facilita extração futura de serviço |
| Persistência de sessão | SQLAlchemy `Session` por request (`get_db`) | Conexão global compartilhada | Evita corrupção de estado entre requisições concorrentes; custo é overhead pequeno de abrir/fechar sessão |
| Exposição externa | Klipper ServiceLB (usa o IP da própria VM) | LoadBalancer externo dedicado da MGC | Sem custo adicional de LB gerenciado — mas o IP da API fica atrelado ao IP da VM; trocar de VM exige atualizar DNS/clientes |
| Ingress | Sem Ingress Controller, serviço exposto direto na porta 80 | NGINX/Traefik Ingress com roteamento por host | Simplicidade — só existe um serviço hoje, não há múltiplos domínios/paths pra rotear |
| Migração de schema | Manual (`Base.metadata.create_all`) | Alembic (versionamento de migrations) | Simplicidade no estágio atual; aceita-se o risco de não ter histórico de mudanças de schema nem rollback controlado |
| Observabilidade | Métricas (Prometheus) + logs estruturados JSON no stdout | APM completo (traces distribuídos) | Cobre os requisitos não-funcionais atuais sem custo de uma ferramenta de tracing; tracing vira necessário se um segundo serviço aparecer |

**Sobre o K3s single-node ser um SPOF:** com um único nó, a VM concentra control
plane e workloads. Isso significa que:
- Reboot de manutenção da MGC, OOM do host ou o processo `k3s` travando derruba
  **as duas réplicas ao mesmo tempo** — as 2 réplicas protegem contra falha de
  *pod*, não de *nó*.
- Não há como fazer `cordon`/`drain` de um nó para manutenção sem downtime, porque
  não existe um segundo nó para receber os pods enquanto isso.
- Essa é uma escolha consciente de custo vs. disponibilidade nesta fase — está
  refletida na meta de 99,5% (e não 99,9%+) e documentada aqui para não ser
  redescoberta como "bug" depois. Migrar para multi-node (ou para MKS) é o caminho
  natural quando a meta de disponibilidade subir.

Deploy e Banco estão detalhados nos ADRs 001 e 002 (`docs/adr/`) — contexto,
alternativas e consequências completas ficam lá; aqui é só o resumo comparativo.

## Pontos de melhoria

### Escalabilidade

A aplicação é stateless, então escala na horizontal — mais réplicas atrás do
balanceador. Hoje são 2 réplicas fixas; o próximo passo natural é o **HPA**
(Horizontal Pod Autoscaler), que ajusta esse número automaticamente pela utilização
de CPU (ex.: mínimo 2, máximo 6, alvo de 70%).

Vale registrar também que mais réplicas não resolvem um gargalo de banco — o
PostgreSQL escala na vertical e costuma saturar primeiro. Antes de configurar o HPA,
o teste de carga (k6, ver Requisitos não-funcionais) precisa mostrar *onde* o sistema
degrada sob 300 req/s: se for CPU da API, o HPA resolve; se for o DBaaS, adicionar
réplicas de API só desloca a fila de espera para as conexões do banco.

Em VM single-node, o HPA também tem um teto físico: réplicas extras continuam
disputando os mesmos 2 vCPU/2 GB do host. Antes de configurar `maxReplicas` alto,
vale validar com `kubectl describe node` quanto de CPU/memória sobra depois do
`k3s` e dos pods atuais — senão o HPA cria pods que ficam `Pending` por falta de
recurso no nó.

### Alta disponibilidade da infraestrutura

Hoje a HA cobre só o nível de pod (2 réplicas). Para cobrir o nível de nó:
- **Curto prazo, sem trocar de topologia:** snapshot/backup periódico da VM K3s
  (estado do cluster, não só da aplicação) para reduzir o tempo de recuperação em
  caso de perda da VM.
- **Médio prazo:** K3s multi-node (mínimo 3 nós para `etcd` com quorum, ou uma
  combinação de server + agents) — os manifests YAML da aplicação não mudam, só a
  topologia do cluster.
- **Alternativa mais simples que multi-node manual:** migrar para MKS (Kubernetes
  Gerenciado da MGC) quando a meta de disponibilidade justificar o custo — já
  planejado como próximo passo no trade-off de Deploy.

### Próximos passos naturais

| Melhoria | Por quê |
|---|---|
| HTTPS / TLS | Toda API em produção deve ser acessada por HTTPS |
| Autoscaler (HPA) | Escala automaticamente conforme a carga |
| Versionamento de API | `/v1/orders` permite evoluir sem quebrar clientes |
| Rate limiting | Evita abuso e protege o banco de sobrecargas |
| Cache (Redis) | Reduz consultas repetidas ao banco |
| Migrações de schema (Alembic) | Controle de versão das mudanças no banco — hoje `create_all` não tem rollback nem histórico |
| Testes de carga | Valida o comportamento sob alto tráfego |
| Migrar para MKS ou K3s multi-node | Quando precisar de HA real: manifests YAML idênticos, só muda a topologia/kubeconfig |
| Testes de integração da camada `repositories` | Hoje os testes sobem a app inteira via `TestClient`; testes focados no repository (com um Postgres real via testcontainers, por exemplo) pegam regressão de query sem depender da camada HTTP |
| `pool_size`/`pool_pre_ping` no SQLAlchemy | Evita conexões mortas com o DBaaS depois de idle prolongado ou failover do banco gerenciado |
| Graceful shutdown | Garantir que o pod termina requisições em andamento antes de morrer em um rolling update (`terminationGracePeriodSeconds` + handler de shutdown do Uvicorn) |
| Backup/restore documentado do DBaaS | Point-in-time recovery testado — hoje o backup automático existe, mas o processo de restauração não está validado nem documentado |
| Secrets fora do `kubectl create secret` manual | Hoje a `DATABASE_URL` é injetada via GitHub Actions a cada deploy; um cofre de secrets (ex. Sealed Secrets, ou o Secrets Manager da MGC) evita depender só da pipeline pra isso existir |
| Alertas (Alertmanager) a partir do `/metrics` | Hoje as métricas existem e os alvos de latência/erro estão definidos, mas não há alerta automático quando o P95 ou a taxa de erro 5xx ultrapassam o limite |

### Custo estimado na Magalu Cloud

| Recurso | Especificação | Observação |
|---|---|---|
| VM K3s | BV2-2-40 (2 vCPU, 2 GB) | Cobrada por hora de uso |
| DBaaS PostgreSQL | Instância pequena | Cobrado por hora de uso |
| Container Registry | Por armazenamento | Baixo para imagens < 500 MB |
