# TCC — Gerenciamento e Monitoramento de Rede
**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 17/04/2026 — rev 2)

---

## Objetivo

Projeto de TCC que compara 3 abordagens de monitoramento de rede aplicadas a uma VNF (Web Application Firewall):

| Abordagem | Mecanismo |
|-----------|-----------|
| **eBPF (BCC)** | Instrumentação em nível de kernel via kprobes |
| **Sysstat** | Polling tradicional em userspace via `/proc` |
| **Prometheus** | Mesma coleta do sysstat + exposição HTTP de métricas |

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── probe.py                   # Probe UDP único (configurado por env vars)
│   ├── vnf/
│   │   ├── waf.py                 # WAF TCP porta 8080
│   │   ├── monitor_ebpf.py        # Monitor eBPF: kprobes sport=8080 + psutil
│   │   ├── monitor_sysstat.py     # Monitor sysstat: /proc/net/dev + psutil
│   │   └── monitor_prometheus.py  # Monitor Prometheus: /proc/net/dev + psutil + HTTP :8000
│   ├── client/
│   │   └── client.py              # Envia NUM_MESSAGES mensagens TCP
│   └── compare.py                 # Consolida resultados em CSV e JSON
├── configs/
│   ├── Dockerfile                 # Ubuntu 24.04 + BCC tools + Python 3
│   └── Dockerfile.client          # Python 3.9 slim
├── docker-compose.ebpf.yml        # Stack isolada eBPF
├── docker-compose.sysstat.yml     # Stack isolada Sysstat
├── docker-compose.prometheus.yml  # Stack isolada Prometheus
├── scripts/
│   ├── run_ebpf.sh                # Executa benchmark eBPF completo
│   ├── run_sysstat.sh             # Executa benchmark Sysstat completo
│   └── run_prometheus.sh          # Executa benchmark Prometheus completo
└── results/
    ├── pre_testes/                 # Resultados preliminares (N=100, N=1000)
    ├── <ferramenta>_<N>_run<ID>_results.json
    ├── comparison_<N>_<RUNS>runs.csv/.json
    └── comparison_all_runs.csv/.json
```

---

## Componentes Implementados

### 1. VNF — Web Application Firewall (`src/vnf/`)

- **`waf.py`** (85 linhas): TCP server na porta 8080
  - Detecta: SQLi, XSS, Path Traversal, RCE, Null Byte
  - Bloqueia ou encaminha requisições; não escreve métricas

- **`monitor_ebpf.py`** (113 linhas): monitor eBPF
  - Kprobes em `tcp_sendmsg` e `tcp_cleanup_rbuf`, filtro `sport=8080`
  - Coleta bytes RX/TX + CPU/mem do WAF via psutil
  - Responde a probes UDP na porta 9999 com JSON de métricas

- **`monitor_sysstat.py`** (83 linhas): monitor sysstat
  - Lê `/proc/net/dev` (interface `lo`)
  - Coleta CPU/mem do WAF via psutil
  - Responde a probes UDP na porta 9999

- **`monitor_prometheus.py`** (100 linhas): monitor Prometheus
  - Mesma lógica do sysstat
  - Expõe Gauges adicionais em `:8000/metrics` via `prometheus_client`

### 2. Probe (`src/probe.py`)

- Script único compartilhado pelos três stacks
- Aguarda o monitor estar pronto (`wait_ready`) antes de iniciar a medição
- Envia requisição UDP ao monitor-server a cada 1s
- Mede RTT (roundtrip time) como métrica principal de overhead
- Configurável via variáveis de ambiente: `COLLECTOR`, `RESULTS_PATH`, `DURATION`, `MONITOR_HOST`, `MONITOR_PORT`
- Handler SIGTERM registrado no início: garante que `save()` é chamado mesmo quando `docker compose down` encerra o container antes de DURATION expirar
- Saída: `results/<ferramenta>_<N>_run<ID>_results.json`

### 3. Geração de Tráfego (`src/client/`)

- **`client.py`** (115 linhas): envia `NUM_MESSAGES` mensagens TCP ao WAF
  - Gera payloads dinamicamente em memória com `random.seed(42)` (sequência reprodutível)
  - 60% conteúdo limpo, 40% padrões maliciosos: SQLi, XSS, RCE, Path Traversal, Null Byte

### 4. Comparação (`src/compare.py`)

Três modos de uso:

| Comando | Descrição | Saída |
|---------|-----------|-------|
| `python3 src/compare.py 100` | Compara 3 ferramentas para N=100 (run 1) | `comparison_100.csv/.json` |
| `python3 src/compare.py 100 5` | Agrega 5 runs de N=100 (média ± desvio) | `comparison_100_5runs.csv/.json` |
| `python3 src/compare.py` | Cross-N com todos os valores disponíveis | `comparison_all_runs.csv/.json` |

- Respeita `RESULTS_SUBDIR` para leitura/escrita em subdiretórios (ex: `pre_testes/`)
- Pré-carrega cada arquivo uma única vez antes do loop de métricas — evita warnings duplicados

---

## Infraestrutura Docker

Três stacks independentes com topologia idêntica:

```
Cliente TCP → WAF (porta 8080) → Monitor-server (UDP :9999)
                                         ↑
                                  probe.py (1 req/s)
```

| Stack | Configuração |
|-------|-------------|
| eBPF | `privileged: true`, `pid: host`, BPF filesystem mounts |
| sysstat / Prometheus | unprivileged, `/proc` montado read-only, `pid: host` |

Variáveis de ambiente relevantes:

| Variável | Padrão | Descrição |
|---|---|---|
| `NUM_MESSAGES` | 100000 | Mensagens TCP enviadas pelo cliente |
| `DURATION` | `NUM_MESSAGES/3500 + 15` | Duração da coleta (segundos) |
| `RUN_ID` | 1 | Identificador do run |
| `WORKERS` | 10 | Threads concorrentes do cliente |
| `RESULTS_SUBDIR` | (vazio) | Subdiretório de resultados (ex: `pre_testes`) |

---

## Resultados (17/04/2026)

> Resultados preliminares estão em `results/pre_testes/` (gerados com flag `--pre`).

### N = 2000 mensagens — 5 runs (média ± desvio entre runs)

| Métrica | eBPF (média ± dp) | Sysstat (média ± dp) | Prometheus (média ± dp) |
|---------|-------------------|----------------------|--------------------------|
| Latência média (ms) | 0.4816 ± 0.1202 | 0.4613 ± 0.0304 | **0.4558 ± 0.0282** ✓ |
| Desvio padrão (ms) | 0.2013 ± 0.2522 | 0.1015 ± 0.1159 | **0.0551 ± 0.0260** ✓ |
| Latência máx (ms) | 3.1734 ± 2.5816 | 1.9079 ± 2.7544 | **0.6873 ± 0.0182** ✓ |
| Latência mín (ms) | 0.2468 ± 0.0242 | 0.2528 ± 0.0331 | **0.2315 ± 0.0493** ✓ |
| Amostras coletadas | 1996.2 | **1997.0** ✓ | **1997.0** ✓ |
| CPU média WAF (%) | 0.058 | **0.050** ✓ | **0.050** ✓ |
| Memória média WAF (MB) | 11.454 | **11.490** ✓ | **11.490** ✓ |

> ✓ Melhor valor na métrica

### N = 50000 mensagens — 5 runs preliminares (Prometheus, `pre_testes/`)

> Executado em 17/04/2026 após correção do bug de TIME_WAIT. Apenas Prometheus disponível por enquanto.

| Métrica | Prometheus (média ± dp) |
|---------|--------------------------|
| Latência média (ms) | 0.8832 ± 0.0126 |
| Desvio padrão (ms) | 0.4390 ± 0.0583 |
| Latência máx (ms) | 2.3655 ± 0.3574 |
| Latência mín (ms) | 0.3113 ± 0.0371 |
| Amostras coletadas | 29.0 ± 0.0 |
| CPU média coletor (%) | 84.49 ± 2.05 |
| Memória média coletor (MB) | 11.68 ± 0.10 |

> Nota: "amostras" = 29 porque DURATION = 50000/3500 + 15 = 29s e o probe coleta 1 amostra/s.

### Observações

- **Prometheus** apresenta a maior consistência em N=2000: latência máxima de 0.69ms (vs 3.17ms do eBPF e 1.91ms do sysstat) e desvio entre runs quase zero (±0.02ms).
- **eBPF** apresenta alta variância nos picos (máx ±2.58ms entre runs), comportamento atribuído à natureza do kprobe sob carga prolongada.
- **sysstat** e **Prometheus** contabilizam todo o tráfego da interface `lo`, incluindo as próprias probes UDP, distorcendo os bytes RX/TX. O eBPF mede com precisão apenas a porta 8080.
- Em N=50000, a CPU do coletor Prometheus sobe para ~85%, indicando overhead significativo do servidor HTTP sob carga alta — dado relevante para a comparação final.

---

## Scripts de Execução

```bash
# Run único
bash scripts/run_ebpf.sh
NUM_MESSAGES=50000 bash scripts/run_sysstat.sh

# Múltiplas repetições (sequencial, salva cada run separado)
bash scripts/run_multi.sh ebpf       100000 5
bash scripts/run_multi.sh sysstat    100000 5
bash scripts/run_multi.sh prometheus 100000 5

# Resultados preliminares (salvos em results/pre_testes/)
bash scripts/run_multi.sh prometheus 50000 5 --pre
```

Nomenclatura dos resultados: `<ferramenta>_<N>_run<ID>_results.json`

Os scripts `run_*.sh` aguardam o container do coletor terminar via `docker wait` (sem sleep fixo) e imprimem os logs do coletor caso o arquivo de resultado não seja encontrado.

---

## Estado Atual

- Branch: `dev/joao`
- Arquitetura: `probe.py` único + monitor por variante

### Correções aplicadas (17/04/2026)

| Componente | Problema | Correção |
|---|---|---|
| `probe.py` | `docker compose down` encerrava o container antes de salvar | Handler SIGTERM registrado: `signal.signal(SIGTERM, lambda *_: sys.exit(0))` dispara o bloco `finally` com `save()` |
| `monitor_prometheus.py` | Porta HTTP 8000 em TIME_WAIT bloqueava o bind do UDP 9999, zerando amostras nos runs pares | UDP 9999 vinculado **antes** do HTTP 8000; HTTP com 30 tentativas (×2s) e fallback sem crash |
| `compare.py` | Warnings de arquivo não encontrado repetindo N×TOOLS×RUNS vezes | Dados pré-carregados por `(tool, run_id)` fora do loop de métricas |
| `run_*.sh` | `sleep` fixo subestimava/superestimava o tempo; falhas silenciosas | `docker wait <collector>` substitui o sleep; resultado verificado explicitamente com logs do coletor em caso de ausência |
| `run_multi.sh` | Sem suporte a subdiretório de resultados | Flag `--pre` redireciona para `results/pre_testes/` via `RESULTS_SUBDIR` |
| `run_*.sh` | `docker compose down --volumes` apagava dados entre runs | Removido `--volumes`; apenas `--remove-orphans` |

### Resultados disponíveis

| N | Ferramenta | Runs | Localização |
|---|---|---|---|
| 2000 | eBPF, sysstat, Prometheus | 5 | `results/` |
| 50000 | Prometheus | 5 (preliminar) | `results/pre_testes/` |
| 100000 | eBPF | 5 (preliminar) | `results/pre_testes/` |
