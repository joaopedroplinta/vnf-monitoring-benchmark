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
              Monitor-server (UDP :9999)
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

- O **WAF** inspeciona cada payload (SQLi, XSS, PathTraversal, RCE, NullByte) e responde ao cliente. Não escreve métricas.
- O **monitor-server** coleta métricas do WAF usando a ferramenta correspondente e responde a qualquer request UDP com um JSON de métricas.
- O **probe** envia requests UDP a cada 1s e mede o tempo de roundtrip — essa latência é a métrica principal de comparação.
- A ferramenta muda entre os testes; o probe é o mesmo script (`probe.py`) nos três casos.

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── probe.py                  # Probe UDP único (configurado por variáveis de ambiente)
│   ├── vnf/
│   │   ├── waf.py                # WAF TCP (porta 8080) — SQLi, XSS, PathTraversal, RCE, NullByte
│   │   ├── monitor_ebpf.py       # Monitor eBPF: kprobes sport=8080 + psutil WAF
│   │   ├── monitor_sysstat.py    # Monitor sysstat: /proc/net/dev + psutil WAF
│   │   └── monitor_prometheus.py # Monitor Prometheus: /proc/net/dev + psutil WAF + HTTP :8000
│   ├── client/
│   │   └── client.py             # Gerador de tráfego TCP (10 workers, ~3500 msg/s)
│   └── compare.py                # Consolida resultados em CSV e JSON (3 modos)
├── configs/
│   ├── Dockerfile                # Imagem base Ubuntu 24.04 + BCC
│   └── Dockerfile.client         # Imagem para o gerador de tráfego
├── scripts/
│   ├── run_ebpf.sh               # Executa o teste completo com eBPF
│   ├── run_sysstat.sh            # Executa o teste completo com sysstat
│   ├── run_prometheus.sh         # Executa o teste completo com Prometheus
│   └── run_multi.sh              # Executa N repetições sequenciais de uma ferramenta
├── docs/
│   └── architecture.md           # Documentação de arquitetura
├── results/                      # Resultados definitivos (*_<N>_run<ID>_results.json, .csv, .json)
│   └── pre_testes/               # Resultados preliminares e experimentais
├── docker-compose.ebpf.yml
├── docker-compose.sysstat.yml
└── docker-compose.prometheus.yml
```

---

## Como Rodar

### Requisitos
- Linux nativo (kernel 6.10+, testado no 6.12).
- Docker + Docker Compose.
- Headers do kernel instalados no host (necessário para o monitor eBPF).

### Executar cada teste

Cada script sobe a stack completa (WAF + monitor-server + cliente + probe), aguarda o coletor finalizar via `docker wait` e exibe um resumo:

```bash
bash scripts/run_ebpf.sh
bash scripts/run_sysstat.sh
bash scripts/run_prometheus.sh
```

Variáveis de ambiente opcionais:

| Variável | Padrão | Descrição |
|---|---|---|
| `NUM_MESSAGES` | 100000 | Mensagens TCP enviadas pelo cliente |
| `DURATION` | `NUM_MESSAGES/3500 + 15` | Duração da coleta (segundos) |
| `RUN_ID` | 1 | Identificador do run |
| `WORKERS` | 10 | Threads concorrentes do cliente |

### Executar múltiplas repetições

```bash
bash scripts/run_multi.sh <ferramenta> <num_messages> <num_runs> [--pre]

# Exemplos:
bash scripts/run_multi.sh ebpf       100000 5
bash scripts/run_multi.sh sysstat    100000 5
bash scripts/run_multi.sh prometheus 100000 5

# Com flag --pre: salva em results/pre_testes/ (testes preliminares)
bash scripts/run_multi.sh prometheus 50000 5 --pre
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
| `monitor_latency_avg_ms` | probe | Latência média da roundtrip UDP (overhead do monitoramento) |
| `monitor_latency_stddev_ms` | probe | Desvio padrão da latência |
| `monitor_latency_max_ms` | probe | Latência máxima observada |
| `monitor_samples` | probe | Número de amostras coletadas |
| `bytes_rx / bytes_tx` | monitor-server | eBPF: kprobe sport=8080; sysstat/Prom: `/proc/net/dev` |
| `cpu_avg_pct` | monitor-server (psutil) | Uso médio de CPU do processo WAF |
| `mem_avg_mb` | monitor-server (psutil) | Uso médio de memória do processo WAF |
| `collector_cpu_avg_pct` | monitor-server (psutil) | Uso médio de CPU do próprio coletor |
| `collector_mem_avg_mb` | monitor-server (psutil) | Uso médio de memória do próprio coletor |

---

## Detalhes dos Monitores

### eBPF (`monitor_ebpf.py`)
- Carrega programa BPF via BCC.
- `kprobe__tcp_sendmsg`: acumula bytes TX quando `sport == 8080` (respostas do WAF).
- `kprobe__tcp_cleanup_rbuf`: acumula bytes RX quando `sport == 8080` (requisições recebidas pelo WAF).
- Filtro `sport=8080` evita dupla contagem no loopback.
- Requer `privileged: true`, `pid: host`, `/sys/kernel/debug`, headers do kernel.

### sysstat (`monitor_sysstat.py`)
- Lê `/proc/net/dev` (interface `lo`) a cada request UDP recebido.
- Retorna delta de bytes RX/TX em relação ao início do teste.
- Requer `pid: host`.

### Prometheus (`monitor_prometheus.py`)
- Mesma lógica de coleta do sysstat.
- Expõe Gauges em `:8000/metrics` via `prometheus_client`.
- Bind do UDP :9999 feito antes do HTTP :8000 para evitar falha por TIME_WAIT entre runs.
- Requer `pid: host`.

---

## Resultados

Resultados preliminares e experimentais estão em `results/pre_testes/`.

### N = 100.000 mensagens — 5 runs (média ± desvio entre runs)

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | **0.8039 ± 0.043** | 0.8995 ± 0.118 | 1.0924 ± 0.160 |
| Desvio padrão (ms) | **0.3922 ± 0.160** | 0.5672 ± 0.324 | 0.7512 ± 0.297 |
| Latência máx (ms) | **2.4065 ± 1.243** | 3.1361 ± 1.797 | 4.4650 ± 1.526 |
| Latência mín (ms) | 0.4033 ± 0.056 | **0.2755 ± 0.061** | 0.4890 ± 0.124 |
| Amostras coletadas | 43 | 43 | 43 |
| CPU média coletor (%) | 70.998 ± 0.611 | **66.828 ± 1.253** | 78.182 ± 5.143 |
| Memória média coletor (MB) | 11.738 ± 0.023 | **11.648 ± 0.066** | 11.808 ± 0.066 |

**Observações:**
- **eBPF** tem a menor latência média e máxima — overhead de coleta mais baixo sob carga alta.
- **sysstat** tem o menor consumo de CPU e memória do coletor — implementação mais leve.
- **Prometheus** apresenta maior variância na CPU (~5%) e na latência, atribuído ao custo adicional do servidor HTTP.
- Bytes RX/TX não são comparáveis entre eBPF e os demais: eBPF mede apenas tráfego do WAF (sport=8080); sysstat/Prometheus medem todo o tráfego da interface loopback.
