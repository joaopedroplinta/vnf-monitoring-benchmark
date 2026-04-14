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
│   │  (200 reqs) │               │  SQLi/XSS/RCE/PathTraversal │  │
│   └─────────────┘               └──────────────┬──────────────┘  │
│                                                │                 │
│                                   salva a cada 2s               │
│                                                │                 │
│                                                ▼                 │
│                                      vnf_metrics.json            │
│                                    (cpu, mem, conexões,          │
│                                     blocked, allowed)            │
│                                                │                 │
│                                           lê o arquivo           │
│                                                │                 │
│                                                ▼                 │
│                                  ┌─────────────────────────┐     │
│                                  │     Monitor UDP          │     │
│                                  │   monitor_server.py      │     │
│                                  │      porta 9999          │     │
│                                  └────────────┬────────────┘     │
│                                               │                  │
│              ┌────────────────────────────────┤                  │
│              │  request/response UDP (1/s)     │                  │
│              │  (latência = tempo de roundtrip)│                  │
│     ─────────┴─────────                       │                  │
│    │                   │                      │                  │
│    ▼                   ▼                      ▼                  │
│ ┌──────────┐    ┌─────────────┐    ┌──────────────────────┐      │
│ │  eBPF    │    │   sysstat   │    │      Prometheus      │      │
│ │  v23     │    │  collector  │    │       exporter       │      │
│ │          │    │             │    │                      │      │
│ │kprobe    │    │/proc/net/dev│    │/proc/net/dev         │      │
│ │tcp_sendmsg    │(interface lo│    │(interface lo)        │      │
│ │tcp_cleanup    │delta RX/TX) │    │delta RX/TX           │      │
│ │_rbuf     │    │             │    │+ HTTP :8000/metrics  │      │
│ │sport=8080│    │             │    │                      │      │
│ └────┬─────┘    └──────┬──────┘    └──────────┬───────────┘      │
│      │                 │                      │                  │
│      ▼                 ▼                      ▼                  │
│ ebpf_results    sysstat_results      prometheus_results          │
│    .json             .json                  .json                │
│      │                 │                      │                  │
│      └─────────────────┴──────────────────────┘                  │
│                              │                                   │
│                              ▼                                   │
│                         compare.py                               │
│                              │                                   │
│                 ┌────────────┴────────────┐                      │
│                 ▼                         ▼                      │
│          comparison.csv           comparison.json                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Componentes

### WAF — `src/vnf/waf.py`
- Servidor TCP na porta 8080.
- Inspeciona cada payload com 5 regras: SQLi, XSS, PathTraversal, RCE, NullByte.
- Thread dedicada salva métricas em `vnf_metrics.json` a cada 2s via psutil (cpu%, mem_mb) e contadores internos (conexões, blocked, allowed).

### Monitor UDP — `src/vnf/monitor_server.py`
- Servidor UDP na porta 9999.
- Lê `vnf_metrics.json` e responde qualquer request com o JSON de métricas.
- É o ponto de medição de latência: os coletores enviam um request UDP e medem o tempo até a resposta.

### Cliente TCP — `src/client/client.py`
- Envia 200 requisições com `payload.bin` para o WAF (1 req/s).
- O mesmo payload é usado nos três testes para garantir tráfego equivalente.

### Coletor eBPF — `src/ebpf/monitor_bcc.py` (v23)
- Carrega programa BPF no kernel via BCC.
- `kprobe__tcp_sendmsg`: acumula bytes TX quando `sport == 8080` (respostas do WAF).
- `kprobe__tcp_cleanup_rbuf`: acumula bytes RX quando `sport == 8080` (requisições recebidas pelo WAF).
- Filtro `sport=8080` evita dupla contagem no loopback.
- Latência medida no userspace (kprobe `udp_recvmsg` não dispara no kernel 6.12+).
- Requer `privileged: true`, `/sys/kernel/debug`, headers do kernel.

### Coletor sysstat — `src/sysstat/collector.py`
- Lê `/proc/net/dev` (interface `lo`) a cada 1s.
- Calcula delta de bytes RX/TX em relação ao início do teste.
- Latência via `time.time_ns()` no request/response UDP.

### Coletor Prometheus — `src/prometheus/exporter.py`
- Mesma lógica de coleta do sysstat (`/proc/net/dev`).
- Expõe Gauges e Histogram de latência em `:8000/metrics` via `prometheus_client`.

### Comparador — `src/compare.py`
- Lê os três arquivos de resultado e gera `comparison.csv` e `comparison.json`.

---

## Comparação Técnica

| Recurso | eBPF (v23) | sysstat | Prometheus |
|---------|------------|---------|------------|
| **Ponto de coleta de bytes** | Kernel (kprobe, sport=8080) | Userspace (/proc/net/dev, lo) | Userspace (/proc/net/dev, lo) |
| **Medição de latência** | Userspace (time.time) | Userspace (time.time_ns) | Userspace (time.time_ns) |
| **Exposição de métricas** | JSON em arquivo | JSON em arquivo | JSON + HTTP :8000/metrics |
| **Overhead de setup** | Alto (privilégios, headers, BCC) | Baixo | Médio (runtime prometheus_client) |
| **Bytes TX medidos** | Só respostas do WAF (~bytes) | Todo o tráfego lo (~MB) | Todo o tráfego lo (~MB) |

---

## Fluxo de Execução

1. Script `run_<ferramenta>.sh` sobe a stack via Docker Compose.
2. WAF inicia na porta 8080; Monitor UDP inicia na porta 9999.
3. Cliente começa a enviar requisições ao WAF.
4. Coletor envia requests UDP ao Monitor a cada 1s e registra latência + bytes.
5. Após 60s de coleta, o coletor salva o resultado em `results/<ferramenta>_results.json`.
6. Após os três testes, `compare.py` consolida os resultados.

---

## Limitações Conhecidas

- A latência do eBPF é medida no userspace (igual aos demais) devido à incompatibilidade do kprobe `udp_recvmsg` com o kernel 6.12+.
- Bytes TX são incomparáveis entre eBPF e os demais: eBPF mede apenas as respostas do WAF; sysstat/Prometheus medem todo o tráfego da interface loopback.
- O overhead de CPU do Prometheus inclui o custo do servidor HTTP, não apenas da coleta.
