# TCC — Gerenciamento e Monitoramento de Rede (eBPF vs Clássicos)

Análise comparativa de desempenho entre três abordagens de monitoramento de rede aplicadas a uma VNF (Virtual Network Function):

1. **eBPF (BCC)**: coleta no nível do kernel via kprobes (`tcp_sendmsg`, `tcp_cleanup_rbuf`).
2. **sysstat**: polling em userspace via `/proc/net/dev`.
3. **Prometheus**: igual ao sysstat, com exposição adicional de métricas via HTTP (`:8000/metrics`).

O foco é medir o **overhead do monitoramento** (latência da coleta) e a **precisão das métricas** ao monitorar um WAF simplificado rodando em Python.

---

## Arquitetura

```
Cliente TCP ──► WAF (porta 8080) ──► vnf_metrics.json
                                           │
                                    Monitor UDP (porta 9999)
                                     lê e serve o JSON
                                      ▲       ▲       ▲
                                   eBPF   sysstat  Prometheus
                                   (medem latência UDP + bytes RX/TX)
```

- O **WAF** inspeciona cada payload e salva métricas (CPU, mem, conexões, blocked/allowed) a cada 2s.
- O **Monitor UDP** lê esse arquivo e responde qualquer request UDP com o JSON — a latência dessa roundtrip é a métrica principal comparada.
- Os **3 coletores** enviam requests UDP a cada 1s e medem o tempo de resposta.
- Bytes RX/TX: eBPF usa kprobes no kernel; sysstat e Prometheus usam `/proc/net/dev`.

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── ebpf/
│   │   └── monitor_bcc.py        # Coletor eBPF v23 (kprobes tcp_sendmsg/tcp_cleanup_rbuf)
│   ├── sysstat/
│   │   └── collector.py          # Coletor via /proc/net/dev + UDP probe
│   ├── prometheus/
│   │   └── exporter.py           # Coletor /proc/net/dev + HTTP exporter (:8000)
│   ├── vnf/
│   │   ├── waf.py                # WAF TCP (porta 8080) — SQLi, XSS, PathTraversal, RCE, NullByte
│   │   └── monitor_server.py     # Servidor de telemetria UDP (porta 9999)
│   ├── client/
│   │   ├── client.py             # Gerador de tráfego TCP → WAF
│   │   └── gen_payload.py        # Gerador do payload.bin
│   └── compare.py                # Consolida resultados em CSV e JSON
├── configs/
│   ├── Dockerfile                # Imagem base Ubuntu 24.04 + BCC
│   └── Dockerfile.client         # Imagem para o gerador de tráfego
├── scripts/
│   ├── run_ebpf.sh               # Executa o teste completo com eBPF
│   ├── run_sysstat.sh            # Executa o teste completo com sysstat
│   └── run_prometheus.sh         # Executa o teste completo com Prometheus
├── results/                      # Resultados gerados (.csv, .json)
├── docker-compose.ebpf.yml
├── docker-compose.sysstat.yml
└── docker-compose.prometheus.yml
```

---

## Como Rodar

### Requisitos
- Linux nativo (kernel 6.10+, testado no 6.12).
- Docker + Docker Compose.
- Headers do kernel instalados no host (necessário para o coletor eBPF).

### Executar cada teste

Cada script sobe a stack completa (WAF + Monitor UDP + Cliente + coletor), aguarda ~120s e exibe um resumo:

```bash
# eBPF
bash scripts/run_ebpf.sh

# sysstat
bash scripts/run_sysstat.sh

# Prometheus
bash scripts/run_prometheus.sh
```

Ou manualmente:
```bash
docker compose -f docker-compose.ebpf.yml up --build -d
docker compose -f docker-compose.ebpf.yml logs -f ebpf-collector
```

### Gerar comparativo

Após rodar os três testes:
```bash
python3 src/compare.py
```

Gera `results/comparison.csv` e `results/comparison.json`.

---

## Métricas Coletadas

| Métrica | Origem | Descrição |
|---------|--------|-----------|
| `monitor_latency_avg_ms` | Todos | Latência média da roundtrip UDP (overhead do monitoramento) |
| `monitor_latency_stddev_ms` | Todos | Desvio padrão da latência |
| `bytes_rx / bytes_tx` | eBPF: kprobe; sysstat/Prom: `/proc/net/dev` | Volume de tráfego processado |
| `cpu_avg_pct` | WAF via psutil | Uso médio de CPU do processo WAF |
| `mem_avg_mb` | WAF via psutil | Uso médio de memória do WAF |
| `waf_blocked / waf_allowed` | WAF | Requisições interceptadas vs. permitidas |

---

## Detalhes dos Coletores

### eBPF (`monitor_bcc.py` — v23)
- Carrega programa BPF via BCC.
- `kprobe__tcp_sendmsg`: conta bytes TX quando `sport == 8080` (WAF enviando resposta).
- `kprobe__tcp_cleanup_rbuf`: conta bytes RX quando `sport == 8080` (WAF lendo requisição).
- Filtragem por `sport=8080` evita dupla contagem no tráfego loopback.
- Latência medida no userspace (kprobe `udp_recvmsg` não dispara no kernel 6.12+).

### sysstat (`collector.py`)
- Lê `/proc/net/dev` (interface `lo`) a cada 1s.
- Calcula delta de bytes RX/TX em relação ao início do teste.
- Latência via `time.time_ns()` no request/response UDP.

### Prometheus (`exporter.py`)
- Mesma lógica de coleta do sysstat.
- Expõe Gauges e Histogram de latência em `:8000/metrics`.

---

## Resultados (última execução — 60s, 60 amostras)

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | 0.301 | 0.332 | 0.308 |
| Desvio padrão (ms) | 0.089 | 0.039 | 0.107 |
| Latência máx (ms) | 0.855 | 0.475 | 0.918 |
| Latência mín (ms) | 0.168 | 0.231 | 0.191 |
| CPU média WAF (%) | 0.33 | 0.33 | 0.83 |
| Memória média WAF (MB) | 15.07 | 15.20 | 15.43 |
| Bytes RX | ~123 MB | ~122 MB | ~122 MB |
| Requisições bloqueadas | 61 | 59 | 59 |
| Requisições permitidas | 1 | 1 | 1 |
