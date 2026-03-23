# Arquitetura do Sistema

## Visão Geral

Os 3 coletores rodam **simultaneamente**, cada um monitorando o socket TCP na porta 9999 de forma independente. Ao final, o `compare.py` consolida os resultados para análise comparativa.

```
┌─────────────────────────────────────────────────────────────┐
│                        VM Ubuntu                            │
│                                                             │
│   ┌────────────┐   TCP/9999   ┌────────────┐               │
│   │  client.py │ ────────────▶│  server.py │               │
│   └────────────┘              └────────────┘               │
│                                     │                       │
│          ┌──────────────────────────┤                       │
│          │     monitoram porta 9999 │                       │
│          ▼                          ▼                       │
│  ┌───────────────┐       ┌─────────────────┐               │
│  │  eBPF         │       │  sysstat        │               │
│  │  monitor_bcc  │       │  collector.py   │               │
│  │               │       │                 │               │
│  │ · kernel hooks│       │ · psutil        │               │
│  │ · tcp_connect │       │ · net_io        │               │
│  │ · sys_sendto  │       │ · proc metrics  │               │
│  │ · sys_recvfrom│       │ · socket probe  │               │
│  └──────┬────────┘       └───────┬─────────┘               │
│         │                        │                          │
│         │              ┌─────────────────┐                  │
│         │              │  Prometheus     │                  │
│         │              │  exporter.py    │                  │
│         │              │                 │                  │
│         │              │ · psutil        │                  │
│         │              │ · gauges/hist   │                  │
│         │              │ · :8000/metrics │                  │
│         │              └───────┬─────────┘                  │
│         │                      │                            │
│         ▼                      ▼                            │
│  ebpf_results.json   sysstat_results.json                   │
│  prometheus_results.json                                    │
│         │                                                   │
│         └──────────────┬────────────────                    │
│                        ▼                                    │
│                  compare.py                                 │
│                        │                                    │
│            ┌───────────┴───────────┐                        │
│            ▼                       ▼                        │
│    comparison.csv          comparison.json                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Fluxo de dados

1. `client.py` abre conexões TCP com `server.py` na porta 9999 e simula tráfego contínuo
2. Os 3 coletores sobem simultaneamente via `docker-compose up`:
   - **eBPF** — intercepta eventos diretamente no kernel via `kprobe`/`perf_buffer`
   - **sysstat** — consulta `psutil` e sonda a porta a cada segundo
   - **Prometheus** — igual ao sysstat, mas também expõe as métricas em `:8000/metrics`
3. Cada coletor salva seu `*_results.json` no volume compartilhado `results_vol` a cada 10 segundos
4. Ao rodar `compare.py`, os 3 JSONs são lidos e consolidados em `comparison.csv` e `comparison.json`

---

## Comparação das abordagens

| Critério              | eBPF                        | sysstat (psutil)          | Prometheus                  |
|-----------------------|-----------------------------|---------------------------|-----------------------------|
| **Nível de coleta**   | Kernel (ring 0)             | Userspace                 | Userspace                   |
| **Granularidade**     | Por syscall / evento        | Por segundo (polling)     | Por scrape (2s)             |
| **Latência**          | Medida real (ns)            | Estimada via probe TCP    | Estimada via probe TCP      |
| **CPU**               | Delta `utime+stime` do task | `cpu_percent()` do psutil | `cpu_percent()` do psutil   |
| **Memória**           | RSS via `mm_struct`         | `memory_info().rss`       | `memory_info().rss`         |
| **Overhead**          | Muito baixo                 | Baixo                     | Baixo                       |
| **Privilégio**        | Root + `privileged`         | Root                      | Root                        |
| **Saída adicional**   | JSON                        | JSON                      | JSON + `/metrics` HTTP      |

---

## Arquivos de resultado

| Arquivo                      | Gerado por            |
|------------------------------|-----------------------|
| `results/ebpf_results.json`       | `src/ebpf/monitor_bcc.py`      |
| `results/sysstat_results.json`    | `src/sysstat/collector.py`     |
| `results/prometheus_results.json` | `src/prometheus/exporter.py`   |
| `results/comparison.csv`          | `src/compare.py`               |
| `results/comparison.json`         | `src/compare.py`               |
