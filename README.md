# TCC — Gerenciamento e Monitoramento de Rede (eBPF vs Clássicos)

Análise comparativa de desempenho entre três abordagens de monitoramento de rede aplicadas a uma VNF (Virtual Network Function):

1. **eBPF (BCC)**: coleta no nível do kernel via kprobes (`tcp_sendmsg`, `tcp_cleanup_rbuf`).
2. **sysstat**: polling em userspace via `/proc/net/dev`.
3. **Prometheus**: igual ao sysstat, com exposição adicional de métricas via HTTP (`:8000/metrics`).

O foco é medir o **overhead do monitoramento** (latência da coleta) ao monitorar um WAF simplificado rodando em Python.

---

## Arquitetura

```
Cliente TCP ──► WAF (porta 8080)
                      ▲
               observa via ferramenta
                      │
              Observador (UDP :9999)
              eBPF | sysstat | Prometheus
              coleta bytes RX/TX + CPU/mem do WAF
                      ▲
               probe UDP (1/s)
               mede latência de roundtrip
                      │
              <ferramenta>_<N>_run<ID>_results.json
                      │
                 compare.py
                      │
         comparison_<N>_<RUNS>runs.csv/.json
```

- O **WAF** inspeciona cada payload (SQLi, XSS, PathTraversal, RCE, NullByte), registra o tempo de inspeção e responde ao cliente.
- O **observador** coleta métricas do WAF usando a ferramenta correspondente e responde a qualquer request UDP com um JSON de métricas.
- O **probe** envia requests UDP a cada 1s e mede o tempo de roundtrip — essa latência é a métrica principal de comparação.
- A ferramenta muda entre os testes; o probe é o mesmo script (`probe.py`) nos três casos.

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── probe.py                   # Probe UDP único (configurado por variáveis de ambiente)
│   ├── vnf/
│   │   ├── waf.py                 # WAF TCP (porta 8080) — SQLi, XSS, PathTraversal, RCE, NullByte
│   │   ├── observador_ebpf.py     # Observador eBPF: kprobes sport=8080 + psutil WAF
│   │   ├── observador_sysstat.py  # Observador sysstat: /proc/net/dev + psutil WAF
│   │   └── observador_prometheus.py # Observador Prometheus: /proc/net/dev + psutil WAF + HTTP :8000
│   ├── client/
│   │   └── client.py              # Envia payloads pré-gerados ao WAF (PAYLOADS_FILE)
│   └── compare.py                 # Consolida resultados em CSV e JSON (3 modos)
├── configs/
│   ├── Dockerfile                 # Imagem base Ubuntu 24.04 + BCC
│   └── Dockerfile.client          # Imagem para o cliente de tráfego
├── data/
│   └── payloads/                  # Arquivos binários de payloads pré-gerados
│       ├── payloads_100000_6040.bin
│       ├── payloads_500000_6040.bin
│       └── payloads_1000000_6040.bin
├── scripts/
│   ├── gen_payloads.py            # Gera arquivos de payloads (executar antes dos testes)
│   ├── run_ebpf.sh                # Executa o teste completo com eBPF
│   ├── run_sysstat.sh             # Executa o teste completo com sysstat
│   ├── run_prometheus.sh          # Executa o teste completo com Prometheus
│   └── run_multi.sh               # Executa N repetições sequenciais de uma ferramenta
├── docs/
│   └── architecture.md            # Documentação de arquitetura
├── results/                       # Resultados (*_<N>_run<ID>_results.json, .csv, .json)
├── docker-compose.ebpf.yml
├── docker-compose.sysstat.yml
└── docker-compose.prometheus.yml
```

---

## Como Rodar

### Requisitos
- Linux nativo (kernel 6.10+, testado no 6.12).
- Docker + Docker Compose.
- Python 3.10+.
- Headers do kernel instalados no host (necessário para o observador eBPF).

### Passo 1 — Gerar os payloads (uma vez)

Os payloads são pré-gerados no host e montados no container do cliente:

```bash
python3 scripts/gen_payloads.py 100000   # → data/payloads/payloads_100000_6040.bin
python3 scripts/gen_payloads.py 500000   # → data/payloads/payloads_500000_6040.bin
python3 scripts/gen_payloads.py 1000000  # → data/payloads/payloads_1000000_6040.bin
```

Opções do gerador:

```bash
python3 scripts/gen_payloads.py <count> [--ratio 60] [--seed 42] [--out FILE]
# --ratio: percentual de mensagens limpas (padrão: 60 → 60% limpos / 40% maliciosos)
# --seed:  semente aleatória para reprodutibilidade (padrão: 42)
```

### Passo 2 — Executar os testes

Cada script sobe a stack completa (WAF + observador + cliente + probe), aguarda o coletor finalizar via `docker wait` e exibe um resumo:

```bash
NUM_MESSAGES=100000 bash scripts/run_ebpf.sh
NUM_MESSAGES=100000 bash scripts/run_sysstat.sh
NUM_MESSAGES=100000 bash scripts/run_prometheus.sh
```

O script deriva automaticamente o arquivo de payloads a partir de `NUM_MESSAGES`. Se o arquivo não existir, o script aborta com a instrução de geração.

Variáveis de ambiente:

| Variável | Padrão | Descrição |
|---|---|---|
| `NUM_MESSAGES` | 100000 | Quantidade de mensagens — usada para DURATION e nomenclatura dos resultados |
| `DURATION` | `NUM_MESSAGES/3500 + 15` | Duração da coleta (segundos) |
| `RUN_ID` | 1 | Identificador do run |
| `WORKERS` | 10 | Threads concorrentes do cliente |
| `PAYLOADS_FILE_HOST` | `data/payloads/payloads_<N>_6040.bin` | Caminho do arquivo de payloads no host (sobrescreve o padrão) |

### Passo 3 — Múltiplas repetições

```bash
bash scripts/run_multi.sh <ferramenta> <num_messages> <num_runs> [--pre]

# Exemplos:
bash scripts/run_multi.sh ebpf       100000 5
bash scripts/run_multi.sh sysstat    100000 5
bash scripts/run_multi.sh prometheus 100000 5

# Com flag --pre: salva em results/pre_testes/ (testes preliminares)
bash scripts/run_multi.sh prometheus 100000 5 --pre
```

Salva cada repetição como `<ferramenta>_<N>_run<ID>_results.json` e gera a agregação ao final.

### Gerar comparativo

```bash
python3 src/compare.py 100000        # compara 3 ferramentas para N=100000 (run 1)
python3 src/compare.py 100000 5      # agrega 5 runs de N=100000 (média ± desvio)
python3 src/compare.py               # cross-N com todos os valores disponíveis
```

---

## Métricas Coletadas

| Métrica | Origem | Descrição |
|---------|--------|-----------|
| `observador_latency_avg_ms` | probe | Latência média da roundtrip UDP (overhead do monitoramento) |
| `observador_latency_stddev_ms` | probe | Desvio padrão da latência |
| `observador_latency_max_ms` | probe | Latência máxima observada |
| `observador_samples` | probe | Número de amostras coletadas |
| `bytes_rx / bytes_tx` | observador | eBPF: kprobe sport=8080; sysstat/Prom: `/proc/net/dev` |
| `cpu_avg_pct` | observador (psutil) | Uso médio de CPU do processo WAF |
| `mem_avg_mb` | observador (psutil) | Uso médio de memória do processo WAF |
| `collector_cpu_avg_pct` | observador (psutil) | Uso médio de CPU do próprio coletor |
| `collector_mem_avg_mb` | observador (psutil) | Uso médio de memória do próprio coletor |
| `inspect_count` | waf → observador | Total de payloads inspecionados no run |
| `inspect_avg_ms` | waf → observador | Tempo médio de inspeção por payload (ms) |
| `inspect_min_ms` | waf → observador | Tempo mínimo de inspeção (ms) |
| `inspect_max_ms` | waf → observador | Tempo máximo de inspeção (ms) |

---

## Detalhes dos Observadores

### eBPF (`observador_ebpf.py`)
- Carrega programa BPF via BCC.
- `kprobe__tcp_sendmsg`: acumula bytes TX quando `sport == 8080` (respostas do WAF).
- `kprobe__tcp_cleanup_rbuf`: acumula bytes RX quando `sport == 8080` (requisições recebidas pelo WAF).
- Filtro `sport=8080` evita dupla contagem no loopback.
- Requer `privileged: true`, `pid: host`, `/sys/kernel/debug`, headers do kernel.

### sysstat (`observador_sysstat.py`)
- Lê `/proc/net/dev` (interface `lo`) a cada request UDP recebido.
- Retorna delta de bytes RX/TX em relação ao início do teste.
- Requer `pid: host`.

### Prometheus (`observador_prometheus.py`)
- Mesma lógica de coleta do sysstat.
- Expõe Gauges em `:8000/metrics` via `prometheus_client`.
- Bind do UDP :9999 feito antes do HTTP :8000 para evitar falha por TIME_WAIT entre runs.
- Requer `pid: host`.

---

## Resultados

> Valores exibidos como **média ± IC95%** (intervalo de confiança de 95%, t de Student, α=0.05).

### N = 100.000 mensagens — 30 runs (26/04/2026)

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | 1.2252 ± 0.0498 | **1.1876 ± 0.0414** | 1.2348 ± 0.0690 |
| Desvio padrão (ms) | 0.9003 ± 0.1402 | **0.8323 ± 0.1306** | 0.8647 ± 0.1148 |
| Latência máx (ms) | 5.5523 ± 0.9028 | 5.2487 ± 0.8089 | **5.0872 ± 0.6464** |
| Latência mín (ms) | 0.5307 ± 0.0148 | 0.5265 ± 0.0226 | **0.4997 ± 0.0332** |
| CPU média WAF (%) | **66.311 ± 2.2258** | 70.008 ± 0.1606 | 68.356 ± 3.2806 |
| Memória média WAF (MB) | 12.194 ± 0.0147 | **12.155 ± 0.0200** | 12.220 ± 0.0206 |
| CPU média coletor (%) | 1.927 ± 2.6211 | 2.860 ± 4.2246 | **1.402 ± 1.8656** |
| Memória média coletor (MB) | 196.474 ± 0.2631 | **13.689 ± 0.0292** | 24.559 ± 0.0563 |

**Observações:**
- As três ferramentas apresentam latências muito próximas — os IC95 se sobrepõem, indicando que a diferença pode não ser estatisticamente significativa em N=100k.
- **CPU do coletor** tem IC95 superior à média nas três ferramentas, refletindo alta variância em runs curtos (~43s).
- **Memória do coletor**: eBPF ~196 MB (BCC carrega runtime do kernel em userspace), sysstat ~13 MB, Prometheus ~24 MB. IC95 estreito confirma estabilidade entre runs.
- **Bytes RX/TX** não são comparáveis entre eBPF e os demais: eBPF mede exclusivamente tráfego TCP do WAF (sport=8080); sysstat/Prometheus medem toda a interface loopback.

### N = 500.000 mensagens — 30 runs (27/04/2026)

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | **1.3380 ± 0.0309** | 1.4053 ± 0.0267 | 1.4381 ± 0.0265 |
| Desvio padrão (ms) | **0.9469 ± 0.0861** | 1.0322 ± 0.0748 | 1.0469 ± 0.0772 |
| Latência máx (ms) | 7.7065 ± 1.0172 | 7.8964 ± 0.8772 | **7.7276 ± 0.9048** |
| Latência mín (ms) | **0.4412 ± 0.0264** | 0.5098 ± 0.0118 | 0.5102 ± 0.0106 |
| CPU média WAF (%) | 72.134 ± 0.176 | 68.301 ± 0.222 | **67.452 ± 0.225** |
| Memória média WAF (MB) | **12.197 ± 0.025** | 12.198 ± 0.022 | 12.210 ± 0.018 |
| CPU média coletor (%) | **0.709 ± 0.876** | 0.749 ± 0.942 | 0.978 ± 1.045 |
| Memória média coletor (MB) | 196.712 ± 0.318 | **13.639 ± 0.024** | 24.606 ± 0.054 |

Em N=500k o eBPF apresenta menor latência média com IC95 que não se sobrepõem aos demais — diferença estatisticamente significativa. Resultados de N=1M pendentes.
