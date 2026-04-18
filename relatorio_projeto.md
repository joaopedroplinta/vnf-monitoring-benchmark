# TCC — Gerenciamento e Monitoramento de Rede
**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 18/04/2026 — rev 4)

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

## Resultados (18/04/2026)

### N = 100.000 mensagens — 5 runs (média ± desvio entre runs)

| Métrica | eBPF (média ± dp) | sysstat (média ± dp) | Prometheus (média ± dp) |
|---------|-------------------|----------------------|--------------------------|
| Latência média (ms) | **0.8039 ± 0.043** | 0.8995 ± 0.118 | 1.0924 ± 0.160 |
| Desvio padrão (ms) | **0.3922 ± 0.160** | 0.5672 ± 0.324 | 0.7512 ± 0.297 |
| Latência máx (ms) | **2.4065 ± 1.243** | 3.1361 ± 1.797 | 4.4650 ± 1.526 |
| Latência mín (ms) | 0.4033 ± 0.056 | **0.2755 ± 0.061** | 0.4890 ± 0.124 |
| Amostras coletadas | 43 ± 0 | 43 ± 0 | 43 ± 0 |
| CPU média WAF (%) | 70.998 ± 0.611 | **66.828 ± 1.253** | 78.182 ± 5.143 |
| Memória média WAF (MB) | 11.738 ± 0.023 | **11.648 ± 0.066** | 11.808 ± 0.066 |
| CPU média coletor (%) | **0.104 ± 0.093** | 0.108 ± 0.097 | 0.088 ± 0.035 |
| Memória média coletor (MB) | 196.458 ± 0.314 | **13.704 ± 0.050** | 24.596 ± 0.162 |

> Nota: DURATION = 100000/3500 + 15 ≈ 43s → 43 amostras por run.

### N = 500.000 mensagens — 5 runs (média ± desvio entre runs)

| Métrica | eBPF (média ± dp) | sysstat (média ± dp) | Prometheus (média ± dp) |
|---------|-------------------|----------------------|--------------------------|
| Latência média (ms) | **0.7691 ± 0.037** | 0.8374 ± 0.016 | 0.9531 ± 0.069 |
| Desvio padrão (ms) | 0.5447 ± 0.140 | **0.5130 ± 0.093** | 0.5694 ± 0.173 |
| Latência máx (ms) | 5.2284 ± 1.584 | 4.7667 ± 1.181 | **4.6328 ± 1.399** |
| Latência mín (ms) | 0.2804 ± 0.056 | **0.2757 ± 0.040** | 0.3025 ± 0.084 |
| Amostras coletadas | 157 ± 0 | 157 ± 0 | 157 ± 0 |
| CPU média WAF (%) | 51.758 ± 0.471 | **50.728 ± 0.378** | 67.384 ± 8.324 |
| Memória média WAF (MB) | 11.722 ± 0.036 | **11.664 ± 0.076** | 11.816 ± 0.046 |
| CPU média coletor (%) | **0.056 ± 0.006** | 2.530 ± 5.523 | 2.906 ± 6.319 |
| Memória média coletor (MB) | 196.182 ± 0.325 | **13.504 ± 0.062** | 24.502 ± 0.125 |

> Nota: DURATION = 500000/3500 + 15 ≈ 157s → 157 amostras por run.

### Observações

- **eBPF** tem a menor latência média em ambos os N — overhead de coleta mais baixo sob carga alta, apesar do custo de setup do kprobe.
- **Memória do coletor eBPF ~196 MB** vs sysstat ~13 MB e Prometheus ~24 MB: custo do BCC carregar o runtime do kernel em espaço de usuário.
- **CPU do coletor eBPF** é extremamente baixa (< 0.1%) porque a coleta ocorre no kernel; sysstat e Prometheus têm variância alta em N=500k (std > 5%), possivelmente por variações no polling de `/proc`.
- **Prometheus** apresenta maior variância na CPU do WAF em N=500k (±8.3%) e na latência, reflexo do custo adicional do servidor HTTP em `:8000/metrics`.
- **Bytes RX/TX não são comparáveis entre eBPF e sysstat/Prometheus** por diferença no ponto de medição. O monitor eBPF intercepta as chamadas de sistema `tcp_sendmsg` e `tcp_cleanup_rbuf` via kprobes com filtro `sport=8080`, contabilizando exclusivamente o tráfego TCP do WAF. Já sysstat e Prometheus leem `/proc/net/dev` na interface `lo`, que agrega *todo* o tráfego da loopback — incluindo as probes UDP na porta 9999 e qualquer outro tráfego da máquina. Comparar os bytes reportados pelas duas abordagens equivale a comparar medições de escopos distintos.

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
| 100000 | eBPF, sysstat, Prometheus | 5 | `results/` |
| 500000 | eBPF, sysstat, Prometheus | 5 | `results/` |
