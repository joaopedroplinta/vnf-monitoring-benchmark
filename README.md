# TCC — Gerenciamento e Monitoramento de Rede

Comparação de ferramentas de monitoramento de sockets TCP:
**eBPF** vs **sysstat/psutil** vs **Prometheus** — coletando as mesmas métricas simultaneamente sobre um socket TCP na porta 9999 e gerando um relatório comparativo ao final.

---

## 📁 Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── ebpf/
│   │   └── monitor_bcc.py        # Coletor via kernel hooks (BCC/eBPF) v13-final
│   ├── sysstat/
│   │   └── collector.py          # Coletor via psutil + medição de socket
│   ├── prometheus/
│   │   └── exporter.py           # Coletor + exporter HTTP :8000/metrics
│   ├── socket/
│   │   ├── server.py             # Servidor TCP porta 9999 (threading por conexão)
│   │   └── client.py             # Cliente TCP: 200 msgs × 1s, 1 conexão por msg
│   └── compare.py                # Gera comparison.csv e comparison.json
├── configs/
│   ├── Dockerfile                # Imagem base (Ubuntu 22.04 + BCC/eBPF + psutil)
│   ├── Dockerfile.client         # python:3.9-slim
│   └── Dockerfile.server         # python:3.9-slim + numpy
├── scripts/
│   └── start.sh                  # Limpa, builda, sobe e para após 16 min
├── results/                      # JSONs e CSVs gerados (gitignored)
├── docker-compose.yml
└── README.md
```

---

## 🚀 Como rodar

```bash
chmod +x scripts/start.sh
./scripts/start.sh
# Para automaticamente após 16 minutos
```

O script executa em sequência:
1. `docker-compose down --volumes` (limpa estado anterior)
2. `docker-compose build`
3. `docker-compose up` (sobe os 6 serviços)
4. Aguarda 16 minutos e para tudo

### Ver os resultados

```bash
cat results/ebpf_results.json
cat results/sysstat_results.json
cat results/prometheus_results.json
cat results/comparison.csv
cat results/comparison.json
```

---

## 📊 Métricas coletadas

Todos os 3 coletores monitoram a **porta 9999** e coletam:

| Métrica          | Descrição                                          |
|------------------|----------------------------------------------------|
| `connections`    | Conexões detectadas no período                     |
| `bytes_tx`       | Total de bytes enviados pelo servidor              |
| `bytes_rx`       | Total de bytes recebidos pelo cliente              |
| `latency_avg_ms` | Latência média TCP (ms)                            |
| `latency_max_ms` | Latência máxima TCP (ms)                           |
| `latency_min_ms` | Latência mínima TCP (ms)                           |
| `cpu_avg_pct`    | CPU médio dos processos monitorados (%)            |
| `mem_avg_mb`     | Memória RSS média dos processos monitorados (MB)   |

---

## 🐳 Serviços Docker

| Serviço                | Container              | Descrição                                        |
|------------------------|------------------------|--------------------------------------------------|
| `server`               | socket-server          | Servidor TCP porta 9999                          |
| `client`               | socket-client          | 200 mensagens, 1s intervalo, 1 conexão por msg   |
| `ebpf-collector`       | ebpf-collector         | Coleta via hooks no kernel (eBPF/BCC)            |
| `sysstat-collector`    | sysstat-collector      | Coleta via psutil + medição de socket            |
| `prometheus-collector` | prometheus-collector   | Coleta + expõe métricas em :8000/metrics         |
| `comparator`           | comparator             | Aguarda 15min e gera relatório CSV/JSON          |

Todos os serviços usam `network_mode: host`. O `ebpf-collector` usa adicionalmente `pid: "host"` e `privileged: true`.

---

## ⚙️ Requisitos

- Docker + Docker Compose (testado com v1.29.2)
- Kernel Linux ≥ 4.9 com suporte a eBPF (testado no 6.8.0-101-generic)
- VM com suporte a `privileged: true` (necessário para BCC/eBPF)
- Ubuntu 22.04 (recomendado)

---

## 🔬 Detalhes técnicos do coletor eBPF

O coletor eBPF (`monitor_bcc.py`) usa os seguintes hooks:

| Hook | Finalidade |
|------|-----------|
| `tracepoint/sock/inet_sock_set_state` | Detecta conexões TCP (`TCP_SYN_SENT`) |
| `tracepoint/syscalls/sys_exit_write` | Captura TX do servidor (filtrado por TGID via psutil) |
| `tracepoint/syscalls/sys_enter_sendto` | Timestamp de envio do cliente (latência) |
| `tracepoint/syscalls/sys_enter_sendmsg` | Timestamp de envio do cliente (latência) |
| `tracepoint/syscalls/sys_exit_recvfrom` | Captura RX real do cliente + calcula latência |

**Nota sobre `connections`:** o eBPF conta cada `TCP_SYN_SENT` individualmente (~2/s durante 900s), enquanto sysstat/Prometheus amostram conexões ativas instantâneas. São semânticas diferentes e ambas válidas — discutidas na análise comparativa.

**Nota sobre TX:** o servidor Python usa `socket.send()` que no kernel 6.8 chama `write()` internamente (não `sendto`/`sendmsg`). O TGID do servidor é detectado via `psutil.net_connections()` na inicialização e injetado diretamente no mapa BPF antes do loop principal.

---

## 📈 Exemplo de resultado (comparison.csv)

```
metrica,ebpf,sysstat,prometheus
connections,1396,1,1
bytes_tx,122467,941168,940634
bytes_rx,15896,1004501,1003903
latency_avg_ms,0.9825,0.2213,0.2332
latency_max_ms,10.3094,2.3898,1.4277
latency_min_ms,0.072,0.0793,0.0468
cpu_avg_pct,0.0,9.9,9.9
mem_avg_mb,8.76,8.76,8.76
duration_s,900.16,889.32,889.61
```