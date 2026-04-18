# Arquitetura do Sistema de Monitoramento Comparativo

## Visão Geral

O sistema avalia três abordagens de monitoramento aplicadas a uma VNF (WAF TCP).
Cada ferramenta é testada isoladamente em sua própria stack Docker, com a mesma
carga de tráfego e duração, para garantir comparação justa.

```
┌──────────────────────────────────────────────────────────────────┐
│                        Host Linux (kernel 6.12+)                 │
│                                                                  │
│   ┌─────────────────────┐  TCP :8080  ┌────────────────────────┐ │
│   │      Cliente        │ ──────────▶ │         WAF            │ │
│   │     client.py       │  10 workers │       waf.py           │ │
│   │  60% limpos         │  concorrentes│ SQLi/XSS/RCE/PathTrav. │ │
│   │  40% maliciosos     │             │   NullByte             │ │
│   │  seed=42 (fixo)     │             └────────────────────────┘ │
│   └─────────────────────┘                       ▲                │
│                                          observa via ferramenta  │
│                                                 │                │
│                    ┌────────────────────────────┴─────────────┐  │
│                    │        Monitor-server (UDP :9999)         │  │
│                    │                                          │  │
│                    │  eBPF variant     monitor_ebpf.py        │  │
│                    │  → kprobes tcp_sendmsg/tcp_cleanup_rbuf  │  │
│                    │  → filtra sport=8080 no kernel           │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │  → psutil CPU/mem do próprio coletor     │  │
│                    │                                          │  │
│                    │  sysstat variant  monitor_sysstat.py     │  │
│                    │  → /proc/net/dev (interface lo)          │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │  → psutil CPU/mem do próprio coletor     │  │
│                    │                                          │  │
│                    │  Prometheus variant monitor_prometheus.py│  │
│                    │  → /proc/net/dev (interface lo)          │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │  → psutil CPU/mem do próprio coletor     │  │
│                    │  → HTTP :8000/metrics                    │  │
│                    └──────────────────┬───────────────────────┘  │
│                                       │                          │
│                          request/response UDP (1/s)              │
│                          latência = tempo de roundtrip           │
│                                       │                          │
│                              ┌────────┴────────┐                 │
│                              │    probe.py      │                 │
│                              │  (mesmo para os │                 │
│                              │   3 variantes)  │                 │
│                              └────────┬────────┘                 │
│                                       │                          │
│                    <ferramenta>_<N>_run<ID>_results.json         │
│                                       │                          │
│                                  compare.py                      │
│                                       │                          │
│              ┌────────────────────────┼────────────────────┐     │
│              ▼                        ▼                    ▼     │
│   comparison_<N>.csv    comparison_<N>_<R>runs.csv  comparison_  │
│   comparison_<N>.json   comparison_<N>_<R>runs.json  all_runs.*  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Componentes

### WAF — `src/vnf/waf.py`
- Servidor TCP na porta 8080, multithreaded (uma thread por conexão).
- Inspeciona cada payload com 5 regras: SQLi, XSS, PathTraversal, RCE, NullByte.
- Não escreve métricas — coletadas externamente pelo monitor-server.

### Monitor-server — `src/vnf/monitor_ebpf.py` | `monitor_sysstat.py` | `monitor_prometheus.py`
- Servidor UDP na porta 9999.
- Coleta métricas do WAF usando a ferramenta correspondente.
- Responde cada request UDP com JSON contendo:
  - `bytes_rx`, `bytes_tx` — tráfego do WAF
  - `cpu_pct`, `mem_mb` — CPU e memória do processo WAF (psutil)
  - `collector_cpu_pct`, `collector_mem_mb` — overhead do próprio coletor (psutil)
- O que muda entre variantes é **como** os bytes RX/TX são coletados:
  - **eBPF**: kprobes no kernel (`tcp_sendmsg`, `tcp_cleanup_rbuf`), filtrando `sport=8080`. Requer `privileged: true`, `pid: host`.
  - **sysstat**: polling de `/proc/net/dev` (interface `lo`), delta desde o início. Requer `pid: host`.
  - **Prometheus**: igual ao sysstat + expõe HTTP `:8000/metrics`. Requer `pid: host`. O socket UDP 9999 é vinculado **antes** do HTTP 8000 para evitar falha de coleta quando a porta HTTP está em TIME_WAIT.

### Probe UDP — `src/probe.py`
- Script único compartilhado pelas 3 variantes, configurado via env vars (`COLLECTOR`, `RESULTS_PATH`, `DURATION`, `MONITOR_HOST`, `MONITOR_PORT`).
- Aguarda o monitor estar pronto (`wait_ready`) antes de iniciar — evita perda de amostras no startup do BPF.
- Handler SIGTERM registrado no início: garante que `finally: save()` é executado mesmo quando `docker compose down` encerra o container antes de DURATION expirar.
- Envia request UDP ao monitor-server a cada 1s e mede a latência de roundtrip.
- Salva resultados em `results/<collector>_<N>_run<ID>_results.json`.

### Cliente TCP — `src/client/client.py`
- Envia `NUM_MESSAGES` requisições TCP ao WAF usando `WORKERS` threads concorrentes (padrão: 10).
- Payloads gerados dinamicamente em memória com `random.seed(42)` para reprodutibilidade.
- Distribuição fixa: 60% limpos / 40% maliciosos (SQLi, XSS, RCE, PathTraversal, NullByte).
- Sem delay entre envios — taxa medida: ~4500 msg/s com 10 workers.

### Comparador — `src/compare.py`

Três modos de uso:

| Comando | Descrição | Saída |
|---------|-----------|-------|
| `python3 src/compare.py <N>` | Compara 3 ferramentas para N mensagens (run 1) | `comparison_<N>.csv/.json` |
| `python3 src/compare.py <N> <RUNS>` | Agrega RUNS repetições (média ± desvio) | `comparison_<N>_<RUNS>runs.csv/.json` |
| `python3 src/compare.py` | Cross-N com todos os valores disponíveis | `comparison_all_runs.csv/.json` |

---

## Comparação Técnica

| Recurso | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| **Ponto de coleta de bytes** | Kernel (kprobe, sport=8080) | Userspace (/proc/net/dev, lo) | Userspace (/proc/net/dev, lo) |
| **CPU/mem do WAF** | psutil (pid: host) | psutil (pid: host) | psutil (pid: host) |
| **CPU/mem do coletor** | psutil (self) | psutil (self) | psutil (self) |
| **Exposição de métricas** | UDP :9999 | UDP :9999 | UDP :9999 + HTTP :8000 |
| **Overhead de setup** | Alto (privilégios, headers, BCC) | Baixo | Médio (runtime prometheus_client) |
| **Bytes medidos** | Só tráfego WAF (sport=8080) | Todo tráfego loopback | Todo tráfego loopback |

---

## Fluxo de Execução

1. Script `run_<ferramenta>.sh` (ou `run_multi.sh`) sobe a stack via Docker Compose.
2. WAF inicia na porta 8080; monitor-server inicia e começa a coletar métricas.
3. Probe aguarda o monitor responder (`wait_ready`) e inicia a medição.
4. Cliente envia `NUM_MESSAGES` requisições concorrentes ao WAF (10 workers por padrão).
5. Probe envia requests UDP ao monitor-server a cada 1s e registra latência + métricas.
6. Após `DURATION` segundos, o probe salva `results/<ferramenta>_<N>_run<ID>_results.json`.
7. `compare.py` consolida os resultados em CSV/JSON para análise.

---

## Limitações Conhecidas

- Bytes RX/TX são incomparáveis entre eBPF e os demais: eBPF mede apenas o tráfego do WAF (sport=8080); sysstat/Prometheus medem todo o tráfego da interface loopback, incluindo as próprias probes UDP.
- O overhead de CPU do Prometheus inclui o custo do servidor HTTP, não apenas da coleta. Em N=50000 (~3500 msg/s), a CPU do coletor Prometheus chega a ~85%.
- CPU/mem via psutil requer `pid: host` — o monitor-server enxerga o processo WAF via namespace de PID do host.
- A taxa de envio (~3500 msg/s) é limitada pelo WAF (Python GIL + inspeção regex); adicionar workers além de 10 não aumenta o throughput.
- A porta HTTP 8000 (Prometheus) pode estar em TCP TIME_WAIT por até 120s entre runs consecutivos. O monitor agora vincula UDP antes do HTTP e tolera falha no bind HTTP sem comprometer a coleta de dados.
