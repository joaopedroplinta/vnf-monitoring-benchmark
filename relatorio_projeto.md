# TCC — Gerenciamento e Monitoramento de Rede
**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 18/04/2026 — rev 3)

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

### N = 100.000 mensagens — 5 runs (média ± desvio entre runs) — **resultado definitivo**

| Métrica | eBPF (média ± dp) | sysstat (média ± dp) | Prometheus (média ± dp) |
|---------|-------------------|----------------------|--------------------------|
| Latência média (ms) | **0.8039 ± 0.043** | 0.8995 ± 0.118 | 1.0924 ± 0.160 |
| Desvio padrão (ms) | **0.3922 ± 0.160** | 0.5672 ± 0.324 | 0.7512 ± 0.297 |
| Latência máx (ms) | **2.4065 ± 1.243** | 3.1361 ± 1.797 | 4.4650 ± 1.526 |
| Latência mín (ms) | 0.4033 ± 0.056 | **0.2755 ± 0.061** | 0.4890 ± 0.124 |
| Amostras coletadas | 43 ± 0 | 43 ± 0 | 43 ± 0 |
| CPU média coletor (%) | 70.998 ± 0.611 | **66.828 ± 1.253** | 78.182 ± 5.143 |
| Memória média coletor (MB) | 11.738 ± 0.023 | **11.648 ± 0.066** | 11.808 ± 0.066 |

> Nota: DURATION = 100000/3500 + 15 = 43s → 43 amostras por run.

### N = 50000 mensagens — 5 runs preliminares (Prometheus, `pre_testes/`)

| Métrica | Prometheus (média ± dp) |
|---------|--------------------------|
| Latência média (ms) | 0.7993 ± 0.061 |
| Latência máx (ms) | 2.4027 ± 1.530 |
| Amostras coletadas | 29 ± 0 |
| CPU média coletor (%) | 66.08 ± 31.94 |

### Observações

- **eBPF** tem a menor latência média (0.80ms) e máxima (2.41ms) em N=100k — overhead de coleta mais baixo sob carga alta, apesar do custo de setup do kprobe.
- **sysstat** tem o menor consumo de CPU (66.8%) e menor memória — implementação mais leve por não ter overhead HTTP.
- **Prometheus** apresenta maior variância na CPU (±5.1%) e na latência (±0.16ms), reflexo do custo adicional do servidor HTTP em `:8000/metrics`.
- **sysstat** e **Prometheus** contabilizam todo o tráfego da interface `lo` (incluindo probes UDP), enquanto o eBPF mede com precisão apenas a porta 8080 — bytes RX/TX não são comparáveis entre as abordagens.
- Resultados anteriores (N=2000, N=50000) e experimentais preservados em `results/pre_testes/`.

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

- Branch: `dev/joao` | PR #15 (código/resultados) e PR #16 (docs README + relatório) abertas para `main`
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
| 100000 | eBPF, sysstat, Prometheus | 5 | `results/` ← **definitivos** |
| 50000 | Prometheus | 5 | `results/pre_testes/` |
| 2000 | eBPF, sysstat, Prometheus | 5 | `results/pre_testes/` |
| 10000 | Prometheus | 5 | `results/pre_testes/` |
