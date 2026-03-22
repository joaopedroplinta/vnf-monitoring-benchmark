# TCC — Gerenciamento e Monitoramento de Rede

Comparação de ferramentas de monitoramento de sockets TCP:
**eBPF** vs **sysstat** vs **Prometheus** — coletando as mesmas métricas simultaneamente e gerando um relatório de comparação.

---

## 📁 Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── ebpf/
│   │   └── monitor_bcc.py        # Coletor via kernel hooks (BCC/eBPF)
│   ├── sysstat/
│   │   └── collector.py          # Coletor via psutil + socket stats
│   ├── prometheus/
│   │   └── exporter.py           # Coletor + exporter HTTP :8000/metrics
│   ├── socket/
│   │   ├── server.py             # Servidor TCP porta 9999
│   │   └── client.py             # Cliente TCP com tráfego simulado
│   └── compare.py                # Gera comparison.csv e comparison.json
├── configs/
│   ├── Dockerfile                # Imagem base (eBPF + Python)
│   ├── Dockerfile.client
│   └── Dockerfile.server
├── scripts/
│   └── compile.sh                # Script de compilação eBPF
├── docs/
│   └── architecture.md           # Arquitetura detalhada
├── docker-compose.yml
└── README.md
```

---

## 🚀 Como rodar

### 1. Subir todos os coletores simultaneamente
```bash
docker-compose up --build
```

### 2. Gerar o relatório de comparação
```bash
docker-compose --profile compare run comparator
```

### 3. Ver os resultados
```bash
# Resultados individuais
cat results/ebpf_results.json
cat results/sysstat_results.json
cat results/prometheus_results.json

# Comparação final
cat results/comparison.csv
cat results/comparison.json
```

---

## 📊 Métricas coletadas

Todos os 3 coletores monitoram a **porta 9999** e coletam:

| Métrica             | Descrição                                 |
|---------------------|-------------------------------------------|
| `connections`       | Número de conexões ativas/detectadas      |
| `bytes_tx`          | Total de bytes enviados                   |
| `bytes_rx`          | Total de bytes recebidos                  |
| `latency_avg_ms`    | Latência média TCP (ms)                   |
| `latency_max_ms`    | Latência máxima TCP (ms)                  |
| `latency_min_ms`    | Latência mínima TCP (ms)                  |
| `cpu_avg_pct`       | CPU médio dos processos (%)               |
| `mem_avg_mb`        | Memória RSS média dos processos (MB)      |

---

## 🐳 Serviços Docker

| Serviço                | Container              | Descrição                              |
|------------------------|------------------------|----------------------------------------|
| `server`               | socket-server          | Servidor TCP porta 9999                |
| `client`               | socket-client          | Cliente com tráfego simulado           |
| `ebpf-collector`       | ebpf-collector         | Coleta via hooks no kernel (eBPF)      |
| `sysstat-collector`    | sysstat-collector      | Coleta via psutil + medição de socket  |
| `prometheus-collector` | prometheus-collector   | Coleta + expõe :8000/metrics           |
| `comparator`           | comparator             | Gera relatório comparativo (CSV/JSON)  |

---

## ⚙️ Requisitos

- Docker + Docker Compose
- Kernel Linux com suporte a eBPF (≥ 4.9)
- VM com `privileged: true` habilitado (necessário para eBPF)
