# TCC — Gerenciamento e Monitoramento de Rede
**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 16/04/2026)

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
│   │   ├── client.py              # Envia NUM_MESSAGES mensagens TCP
│   │   └── gen_payload.py         # Gera payload.bin (60% limpo + 40% malicioso)
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
    ├── ebpf_results.json
    ├── sysstat_results.json
    ├── prometheus_results.json
    ├── comparison.csv
    └── comparison.json
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
- **`gen_payload.py`** (75 linhas): gera `payload.bin` com seed fixa para reprodutibilidade:
  - 60% conteúdo limpo (texto, números, pontuação aleatórios)
  - 40% padrões maliciosos: SQLi, XSS, RCE, Path Traversal, Null Byte

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

## Resultados (16/04/2026)

### N = 100 mensagens (run 1)

| Métrica | eBPF | Sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | 0.4347 | 0.4510 | **0.3779** ✓ |
| Desvio padrão (ms) | **0.0290** ✓ | 0.0603 | 0.0923 |
| Latência mín (ms) | 0.2854 | 0.2464 | **0.2261** ✓ |
| Latência máx (ms) | **0.4772** ✓ | 0.6338 | 0.6418 |
| Amostras coletadas | **100** ✓ | **100** ✓ | **100** ✓ |
| Bytes RX | 89 338 | 160 987 | 159 173 |
| Bytes TX | 1 202 † | 160 987 | 159 173 |
| CPU média WAF (%) | 0.05 | **0.04** ✓ | 0.05 |
| Memória média WAF (MB) | **11.29** ✓ | 11.37 | 11.47 |
| Duração (s) | 100.08 | 100.08 | 100.07 |

### N = 1000 mensagens (run 1)

| Métrica | eBPF | Sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | **0.4071** ✓ | 0.4531 | 0.4760 |
| Desvio padrão (ms) | 0.0833 | 0.1221 | **0.0401** ✓ |
| Latência mín (ms) | **0.1840** ✓ | 0.2120 | 0.2587 |
| Latência máx (ms) | **1.2971** ✓ | 2.9097 | 0.8506 |
| Amostras coletadas | 999 | 999 | 999 |
| Bytes RX | 868 696 | 1 794 483 | 1 593 103 |
| Bytes TX | 12 325 † | 1 794 483 | 1 593 103 |
| CPU média WAF (%) | **0.05** ✓ | **0.05** ✓ | **0.05** ✓ |
| Memória média WAF (MB) | 11.50 | **11.49** ✓ | **11.49** ✓ |
| Duração (s) | 1000.14 | 1000.19 | 1000.22 |

> ✓ Melhor valor na métrica
> † eBPF mede apenas o lado servidor (`sport=8080`), resultando em TX menor

### Observações

- Os três coletores atingem latências médias comparáveis (~0.38–0.48ms), evidenciando overhead de monitoramento baixo em todos os casos.
- **eBPF** lidera em latência média com N=1000 (0.41ms) e apresenta máx muito abaixo do sysstat (1.3ms vs 2.9ms).
- **sysstat** com N=1000 apresenta maior instabilidade (stddev 0.12ms, máx 2.9ms), reflexo do polling `/proc` sob carga prolongada.
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

- Branch: `dev/joao`, PR #11 aberta para `main`
- Arquitetura: `probe.py` único + monitor por variante
- Correção: `wait_ready()` em `probe.py` garante amostras completas para todos os coletores
- Resultados: gerados e validados para N=100 e N=1000 (run1 cada ferramenta)
- Suporte a múltiplos runs com agregação estatística entre repetições
- Total de código: ~820 linhas Python em 8 arquivos
