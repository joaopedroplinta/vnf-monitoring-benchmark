# TCC — Gerenciamento e Monitoramento de Rede

Comparação de ferramentas de monitoramento de sockets TCP:
**eBPF** vs **sysstat/psutil** vs **Prometheus** — coletando as mesmas métricas simultaneamente sobre um socket TCP na porta 9999 e gerando um relatório comparativo ao final.

---

## 📁 Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── ebpf/
│   │   └── monitor_bcc.py        # Coletor via kernel hooks (BCC/eBPF) v14-final
│   ├── sysstat/
│   │   └── collector.py          # Coletor via psutil + medição de socket
│   ├── prometheus/
│   │   └── exporter.py           # Coletor + exporter HTTP :8000/metrics
│   ├── socket/
│   │   ├── server.py             # Servidor TCP porta 9999 (threading por conexão)
│   │   └── client.py             # Cliente TCP: 200 msgs × 1s, 1 conexão por msg
│   └── compare.py                # Gera comparison.csv e comparison.json
├── configs/
│   ├── Dockerfile                # Imagem base (Ubuntu 24.04 + BCC/eBPF + psutil)
│   ├── Dockerfile.client         # python:3.9-slim
│   └── Dockerfile.server         # python:3.9-slim + numpy
├── scripts/
│   └── start.sh                  # Limpa, builda, sobe e para após 9 min
├── results/                      # JSONs e CSVs gerados (gitignored)
├── docker-compose.yml
└── README.md
```

---

## 🚀 Como rodar

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

O script abrirá um **Menu Interativo** com as seguintes opções:

1.  **Rodar TODOS simultaneamente:** Executa os 3 coletores ao mesmo tempo (comportamento padrão). Útil para comparar o overhead sob as mesmas condições de tempo.
2.  **Rodar Individualmente (eBPF, sysstat ou Prometheus):** Executa apenas o coletor selecionado junto com o servidor e cliente por 8 minutos.
3.  **Rodar Sequencialmente:** Executa um coletor por vez, automaticamente, limpando o ambiente entre as rodadas. Evita interferência de CPU/Memória entre os coletores.
4.  **Apenas gerar relatório:** Processa os arquivos JSON existentes na pasta `results/` e regera o CSV de comparação.

### Fluxo de execução (Opção 1)
1. `docker-compose down --volumes` (limpa estado anterior)
2. `docker-compose up` (sobe os serviços necessários)
3. Aguarda o tempo de coleta (8 min) e gera o relatório final.
4. Para os containers.

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
| `comparator`           | comparator             | Aguarda 8min e gera relatório CSV/JSON           |

Todos os serviços usam `network_mode: host`. O `ebpf-collector` usa adicionalmente `pid: "host"` e `privileged: true`.

---

## ⚙️ Requisitos

- Docker + Docker Compose (testado com v1.29.2)
- Kernel Linux ≥ 4.9 com suporte a eBPF (testado no 6.8.0-101-generic e 6.10+)
- VM com suporte a `privileged: true` (necessário para BCC/eBPF)
- Ubuntu 24.04 (recomendado)

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

**Compatibilidade Kernel 6.10+:** O coletor inclui um workaround para o erro de compilação BCC relacionado à `struct bpf_wq` em kernels recentes.

**Nota sobre `connections`:** O coletor eBPF agora expõe duas métricas separadas:
- `connections_total`: contador cumulativo de `TCP_SYN_SENT` (semântica eBPF pura).
- `connections_active`: snapshot instantâneo via `psutil` (compatível com a semântica do sysstat e Prometheus).

**Nota sobre TX:** o servidor Python usa `socket.send()` que no kernel 6.8+ chama `write()` internamente (não `sendto`/`sendmsg`). O TGID do servidor é detectado via `psutil.net_connections()` na inicialização e injetado diretamente no mapa BPF antes do loop principal.

---

## 📈 Exemplo de resultado (comparison.csv)

```
metrica,ebpf,sysstat,prometheus
connections,0,1,1
bytes_tx,83845,573892,572338
bytes_rx,5431,1522796,1519920
latency_avg_ms,0.3922,0.0625,0.0631
latency_max_ms,0.5759,0.3758,0.3925
latency_min_ms,0.2156,0.0339,0.0532
cpu_avg_pct,0.09,10.0,10.0
mem_avg_mb,9.04,9.04,9.04
duration_s,481.09,475.2,474.3
```