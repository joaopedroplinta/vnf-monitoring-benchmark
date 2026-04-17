# TCC — Gerenciamento e Monitoramento de Rede
**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 17/04/2026)

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

### 2. Probe (`src/probe.py` — 115 linhas)

- Script único compartilhado pelos três stacks
- Aguarda o monitor estar pronto (`wait_ready`) antes de iniciar a medição
- Envia requisição UDP ao monitor-server a cada 1s
- Mede RTT (roundtrip time) como métrica principal de overhead
- Configurável via variáveis de ambiente: `NUM_MESSAGES`, `DURATION`, `RUN_ID`
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

Variáveis de ambiente: `NUM_MESSAGES` (padrão 100), `DURATION` (padrão = `NUM_MESSAGES`)

---

## Resultados (17/04/2026)

> Resultados preliminares (N=100 e N=1000, run único) estão em `results/pre_testes/`.

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

### Observações

- **Prometheus** apresenta a maior consistência em N=2000: latência máxima de 0.69ms (vs 3.17ms do eBPF e 1.91ms do sysstat) e desvio entre runs quase zero (±0.02ms).
- **eBPF** apresenta alta variância nos picos (máx ±2.58ms entre runs), comportamento atribuído à natureza do kprobe sob carga prolongada.
- **sysstat** e **Prometheus** contabilizam todo o tráfego da interface `lo`, incluindo as próprias probes UDP, distorcendo os bytes RX/TX. O eBPF mede com precisão apenas a porta 8080.
- **Correção aplicada:** `probe.py` aguarda prontidão do monitor (`wait_ready`) antes de iniciar o timer, eliminando perda de amostras no startup do BPF (~9s de compilação JIT do kernel).

---

## Scripts de Execução

```bash
# Run único
bash scripts/run_ebpf.sh
NUM_MESSAGES=1000 bash scripts/run_sysstat.sh

# Múltiplas repetições (sequencial, salva cada run separado)
bash scripts/run_multi.sh ebpf       100 5
bash scripts/run_multi.sh sysstat    100 5
bash scripts/run_multi.sh prometheus 100 5
```

Nomenclatura dos resultados: `<ferramenta>_<N>_run<ID>_results.json`

---

## Estado Atual

- Branch: `dev/joao`, PR #13 aberta para `main`
- Arquitetura: `probe.py` único + monitor por variante
- Correção: `wait_ready()` em `probe.py` garante amostras completas para todos os coletores
- Resultados: N=2000 com 5 runs por ferramenta (eBPF, sysstat, Prometheus)
- Resultados preliminares (N=100, N=1000) preservados em `results/pre_testes/`
- Suporte a múltiplos runs com agregação estatística (média ± desvio entre runs)
- Total de código: ~770 linhas Python em 7 arquivos
