# TCC — Gerenciamento e Monitoramento de Rede (eBPF vs Clássicos)

Este projeto realiza uma análise comparativa de desempenho entre três abordagens de monitoramento de rede e sistemas:
1. **eBPF (BCC)**: Coleta de métricas diretamente no nível do kernel.
2. **Sysstat (psutil)**: Coleta tradicional via polling em userspace.
3. **Prometheus**: Exportação de métricas via HTTP para sistemas de monitoramento modernos.

O foco é medir o impacto e a precisão ao monitorar uma **VNF (Virtual Network Function)**, especificamente um **WAF (Web Application Firewall)** simplificado rodando em Python.

---

## 📁 Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── ebpf/
│   │   └── monitor_bcc.py        # Coletor eBPF v19 (Kprobes / Sockets)
│   ├── sysstat/
│   │   └── collector.py          # Coletor via psutil + UDP Probes
│   ├── prometheus/
│   │   └── exporter.py           # Coletor Prometheus + HTTP Exporter
│   ├── vnf/
│   │   ├── waf.py                # Web Application Firewall (TCP 8080)
│   │   └── monitor_server.py     # Servidor de Telemetria (UDP 9999)
│   ├── client/
│   │   └── client.py             # Gerador de tráfego (Payloads SQLi/XSS)
│   └── compare.py                # Consolidador de resultados (CSV/JSON)
├── configs/
│   ├── Dockerfile                # Imagem base Ubuntu 24.04 + BCC
│   └── Dockerfile.client         # Imagem para o gerador de tráfego
├── results/                      # Relatórios gerados (.csv, .json)
├── docker-compose.ebpf.yml       # Stack completa para teste eBPF
└── README.md
```

---

## 🚀 Como rodar os testes

### 1. Requisitos
- WSL2 (Windows) ou Linux Nativo (Kernel 5.15+).
- Docker + Docker Compose.
- Headers do kernel instalados no host.

### 2. Execução (Exemplo eBPF)
Para rodar a bateria de testes usando o coletor eBPF:

```bash
# Sobe a stack (WAF + Coletor + Cliente)
docker compose -f docker-compose.ebpf.yml up --build -d

# Acompanha o progresso
docker compose -f docker-compose.ebpf.yml logs -f ebpf-collector
```

### 3. Gerar Comparativo
Após rodar os três coletores (ebpf, sysstat, prometheus), gere o relatório final:

```bash
python3 src/compare.py
```

Os resultados estarão em `results/comparison.csv`.

---

## 📊 Métricas coletadas

| Métrica | Origem | Descrição |
|---------|--------|-----------|
| `monitor_latency_avg_ms` | eBPF/Probe | Latência do próprio sistema de monitoramento |
| `cpu_avg_pct` | psutil | Uso de CPU médio da VNF (WAF) |
| `bytes_rx / bytes_tx` | VNF/Kernel | Volume de tráfego processado |
| `waf_blocked` | WAF | Requisições maliciosas interceptadas |

---

## 🔬 Detalhes técnicos do coletor eBPF

O coletor eBPF (`monitor_bcc.py`) foi otimizado para rodar em ambientes **WSL2** e kernels modernos (6.6+):

- **Hooks**: Utiliza `kprobe` e `kretprobe` nas funções `sock_sendmsg` e `sock_recvmsg` do kernel.
- **Filtragem**: Injeção dinâmica de PID para monitorar apenas o tráfego do processo de telemetria.
- **Estabilidade**: Resolve problemas de caminhos de headers do kernel no WSL2 via variável de ambiente `BCC_KERNEL_SOURCE`.

---

## 📈 Resultados esperados
Espera-se que o eBPF apresente a menor latência de coleta e o menor overhead de CPU em comparação com as abordagens de polling em userspace, especialmente sob alta carga de tráfego no WAF.
