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
│   │     client.py       │ 200 workers │       waf.py           │ │
│   │  60% limpos         │  asyncio    │ SQLi/XSS/RCE/PathTrav. │ │
│   │  40% maliciosos     │             │   NullByte             │ │
│   │  seed=42 (fixo)     │             └────────────────────────┘ │
│   └─────────────────────┘                       ▲                │
│                                          observa via ferramenta  │
│                                                 │                │
│                    ┌────────────────────────────┴─────────────┐  │
│                    │        Monitor-server (UDP :9999)         │  │
│                    │                                          │  │
│                    │  eBPF variant     observador_ebpf.py        │  │
│                    │  → kprobes tcp_sendmsg/tcp_cleanup_rbuf  │  │
│                    │  → filtra sport=8080 no kernel           │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │  → psutil CPU/mem do próprio coletor     │  │
│                    │                                          │  │
│                    │  sysstat variant  observador_sysstat.py     │  │
│                    │  → /proc/net/dev (interface lo)          │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │  → psutil CPU/mem do próprio coletor     │  │
│                    │                                          │  │
│                    │  Prometheus variant observador_prometheus.py│  │
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
- Servidor TCP na porta 8080, asyncio + ThreadPoolExecutor (workers = `WAF_INSPECT_WORKERS`, padrão: `os.cpu_count()`).
- Inspeciona cada payload com 5 regras: SQLi, XSS, PathTraversal, RCE, NullByte; escreve timing em `waf_metrics.json` a cada 100 requisições.
- Não expõe UDP — métricas coletadas externamente pelo Observador.

### Observador — `src/vnf/observador_ebpf.py` | `observador_sysstat.py` | `observador_prometheus.py`
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
- Envia request UDP ao Observador a cada 1s e mede a latência de roundtrip.
- Salva resultados em `results/<collector>_<N>_run<ID>_results.json`.

### Cliente TCP — `src/client/client.py`
- Envia `NUM_MESSAGES` mensagens ao WAF usando `WORKERS` coroutines asyncio com conexões persistentes (padrão: 200).
- Payloads pré-gerados em disco (`data/payloads/`), carregados via fila asyncio de tamanho fixo (`QUEUE_SIZE=2000`) — RAM constante independente de N.
- Distribuição fixa: 60% benignos / 40% maliciosos (SQLi, XSS, RCE, PathTraversal, NullByte), semente fixa e reprodutível.
- Framing 4-byte big-endian sobre TCP persistente — sem handshake por mensagem.

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
2. WAF inicia na porta 8080; Observador inicia e começa a coletar métricas.
3. Probe aguarda o monitor responder (`wait_ready`) e inicia a medição.
4. Cliente envia `NUM_MESSAGES` mensagens ao WAF via asyncio com 200 workers (conexões persistentes, framing 4-byte).
5. Probe envia requests UDP ao Observador a cada 1s e registra latência + métricas.
6. Após `DURATION` segundos, o probe salva `results/<ferramenta>_<N>_run<ID>_results.json`.
7. `compare.py` consolida os resultados em CSV/JSON para análise.

---

## Limitações Conhecidas

- Bytes RX/TX são incomparáveis entre eBPF e os demais: eBPF filtra `sport=8080` no kernel e mede apenas o tráfego do WAF; sysstat/Prometheus lêem `/proc/net/dev` (interface `lo`) e capturam todo o tráfego loopback, incluindo as próprias probes UDP.
- O overhead de CPU do Prometheus inclui o custo do servidor HTTP (:8000/metrics), não apenas da coleta de bytes.
- CPU/mem via psutil requer `pid: host` — o Observador enxerga o processo WAF via namespace de PID do host.
- A taxa efetiva de inspeção é limitada pelo WAF (Python GIL + regex); aumentar `WORKERS` além de 200 não eleva o throughput pois o gargalo está na inspeção, não no transporte.
- A porta HTTP 8000 (Prometheus) pode estar em TCP TIME_WAIT por até 120s entre runs consecutivos. O monitor agora vincula UDP antes do HTTP e tolera falha no bind HTTP sem comprometer a coleta de dados.
