# Arquitetura do Sistema de Monitoramento Comparativo

## Visão Geral

O sistema avalia três abordagens de monitoramento aplicadas a uma VNF (WAF TCP).
Cada ferramenta é testada isoladamente em sua própria stack Docker, com a mesma
carga de tráfego e duração, para garantir comparação justa.

```
┌──────────────────────────────────────────────────────────────────┐
│                        Host Linux (kernel 6.12+)                 │
│                                                                  │
│   ┌─────────────┐   TCP :8080   ┌─────────────────────────────┐  │
│   │   Cliente   │ ────────────▶ │            WAF              │  │
│   │  client.py  │  payload.bin  │          waf.py             │  │
│   └─────────────┘               │  SQLi/XSS/RCE/PathTraversal │  │
│                                 └─────────────────────────────┘  │
│                                           ▲                      │
│                                    observa via ferramenta        │
│                                           │                      │
│                    ┌──────────────────────┴───────────────────┐  │
│                    │          Monitor-server (UDP :9999)       │  │
│                    │                                          │  │
│                    │  eBPF variant     monitor_ebpf.py        │  │
│                    │  → kprobes tcp_sendmsg/tcp_cleanup_rbuf  │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │                                          │  │
│                    │  sysstat variant  monitor_sysstat.py     │  │
│                    │  → /proc/net/dev (interface lo)          │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │                                          │  │
│                    │  Prometheus variant monitor_prometheus.py│  │
│                    │  → /proc/net/dev (interface lo)          │  │
│                    │  → psutil CPU/mem do processo WAF        │  │
│                    │  → HTTP :8000/metrics                    │  │
│                    └──────────────────┬───────────────────────┘  │
│                                       │                          │
│                          request/response UDP (1/s)              │
│                          (latência = tempo de roundtrip)         │
│                                       │                          │
│                              ┌────────┴────────┐                 │
│                              │    probe.py      │                 │
│                              │  (mesmo para    │                 │
│                              │  os 3 testes)   │                 │
│                              └────────┬────────┘                 │
│                                       │                          │
│              ┌────────────────────────┤                          │
│              │                        │                          │
│              ▼                        ▼                          │
│   ebpf_results.json       sysstat_results.json                   │
│   prometheus_results.json                                        │
│              │                        │                          │
│              └────────────┬───────────┘                          │
│                           ▼                                      │
│                       compare.py                                 │
│                           │                                      │
│              ┌────────────┴────────────┐                         │
│              ▼                         ▼                         │
│       comparison.csv           comparison.json                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Componentes

### WAF — `src/vnf/waf.py`
- Servidor TCP na porta 8080.
- Inspeciona cada payload com 5 regras: SQLi, XSS, PathTraversal, RCE, NullByte.
- Não escreve métricas — essas são coletadas externamente pelo monitor-server.

### Monitor-server — `src/vnf/monitor_ebpf.py` | `monitor_sysstat.py` | `monitor_prometheus.py`
- Servidor UDP na porta 9999.
- Coleta ativamente métricas do WAF usando a ferramenta correspondente.
- Responde cada request UDP com JSON contendo `bytes_rx`, `bytes_tx`, `cpu_pct`, `mem_mb`.
- É o ponto de medição de latência: o probe envia um request UDP e mede o tempo até a resposta.
- O que muda entre variantes é **como** os bytes RX/TX são coletados:
  - **eBPF**: kprobes no kernel (`tcp_sendmsg`, `tcp_cleanup_rbuf`), filtrando `sport=8080`. Requer `privileged: true`, `pid: host`.
  - **sysstat**: polling de `/proc/net/dev` (interface `lo`), delta desde o início do teste. Requer `pid: host`.
  - **Prometheus**: igual ao sysstat + expõe HTTP `:8000/metrics`. Requer `pid: host`.
- CPU/mem do processo WAF coletados via psutil em todas as variantes.

### Probe UDP — `src/probe.py`
- Único script de probe, configurado via variáveis de ambiente (`COLLECTOR`, `RESULTS_PATH`, `DURATION`).
- Envia request UDP ao monitor-server a cada 1s e mede a latência de roundtrip.
- Registra as métricas retornadas na resposta.
- Salva resultados em `results/<collector>_results.json`.

### Cliente TCP — `src/client/client.py`
- Envia requisições TCP com `payload.bin` para o WAF.
- Distribuição 60/40 (maliciosos/benignos) com seed fixa para reprodutibilidade.

### Comparador — `src/compare.py`
- Lê os três arquivos de resultado e gera `comparison.csv` e `comparison.json`.

---

## Comparação Técnica

| Recurso | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| **Ponto de coleta de bytes** | Kernel (kprobe, sport=8080) | Userspace (/proc/net/dev, lo) | Userspace (/proc/net/dev, lo) |
| **CPU/mem do WAF** | psutil (pid: host) | psutil (pid: host) | psutil (pid: host) |
| **Exposição de métricas** | UDP :9999 | UDP :9999 | UDP :9999 + HTTP :8000 |
| **Overhead de setup** | Alto (privilégios, headers, BCC) | Baixo | Médio (runtime prometheus_client) |
| **Bytes medidos** | Só tráfego WAF (sport=8080) | Todo tráfego loopback | Todo tráfego loopback |

---

## Fluxo de Execução

1. Script `run_<ferramenta>.sh` sobe a stack via Docker Compose.
2. WAF inicia na porta 8080; monitor-server inicia e começa a coletar métricas.
3. Cliente começa a enviar requisições ao WAF.
4. Probe envia requests UDP ao monitor-server a cada 1s e registra latência + métricas.
5. Após o tempo configurado, o probe salva o resultado em `results/<ferramenta>_results.json`.
6. Após os três testes, `compare.py` consolida os resultados.

---

## Limitações Conhecidas

- A latência do eBPF é medida no userspace (igual aos demais) devido à incompatibilidade do kprobe `udp_recvmsg` com o kernel 6.12+.
- Bytes RX/TX são incomparáveis entre eBPF e os demais: eBPF mede apenas o tráfego do WAF (sport=8080); sysstat/Prometheus medem todo o tráfego da interface loopback.
- O overhead de CPU do Prometheus inclui o custo do servidor HTTP, não apenas da coleta.
- CPU/mem via psutil requer `pid: host` — o monitor-server enxerga o processo WAF via namespace de PID do host.
