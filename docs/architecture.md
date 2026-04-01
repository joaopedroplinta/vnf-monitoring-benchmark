# Arquitetura do Sistema de Monitoramento Comparativo

## Visão Geral

O sistema avalia o desempenho de funções de rede virtuais (VNF) através de três metodologias de monitoramento simultâneas. O cenário de teste utiliza um **Web Application Firewall (WAF)** como alvo do monitoramento.

```
┌─────────────────────────────────────────────────────────────┐
│                        Ambiente (WSL2/Linux)                │
│                                                             │
│   ┌────────────┐   HTTP/TCP   ┌──────────────┐              │
│   │  Gerador   │ ────────────▶│     WAF      │              │
│   │ de Tráfego │              │ (Porta 8080) │              │
│   └────────────┘              └──────┬───────┘              │
│                                      │                      │
│          ┌───────────────────────────┤                      │
│          │ exporta métricas (UDP 9999)│                      │
│          ▼                           ▼                      │
│  ┌───────────────┐        ┌─────────────────┐               │
│  │  eBPF (BCC)   │        │  Monitor Trad.  │               │
│  │  v19          │        │  (Sysstat/Prom) │               │
│  │               │        │                 │               │
│  │ · sock_hooks  │        │ · psutil        │               │
│  │ · kprobes     │        │ · polling       │               │
│  │ · PID Filter  │        │ · UDP probes    │               │
│  └──────┬────────┘        └───────┬─────────┘               │
│         │                         │                         │
│         ▼                         ▼                         │
│  ebpf_results.json        sysstat_results.json              │
│                           prometheus_results.json           │
│         │                         │                         │
│         └──────────────┬──────────┘                         │
│                        ▼                                    │
│                  compare.py                                 │
│                        │                                    │
│            ┌───────────┴───────────┐                        │
│            ▼                       ▼                        │
│    comparison.csv          comparison.json                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Componentes

### 1. VNF Alvo (WAF)
Localizado em `src/vnf/waf.py`. Inspeciona payloads TCP em busca de padrões SQLi, XSS, etc. Inclui uma pequena carga computacional artificial para tornar o uso de CPU mensurável.

### 2. Servidor de Telemetria
Localizado em `src/vnf/monitor_server.py`. Recebe requisições UDP na porta 9999 e responde com um JSON contendo as métricas internas do WAF (bytes processados, conexões, CPU).

### 3. Coletores
- **eBPF**: Intercepta as funções `sock_sendmsg` e `sock_recvmsg` no kernel para medir a latência exata do processo de monitoramento sem depender de relógios de userspace.
- **Sysstat/Prometheus**: Utilizam a biblioteca `psutil` para ler dados do `/proc` e realizam probes UDP manuais para medir latência (RTT).

---

## Comparação Técnica

| Recurso | eBPF (BCC) | Sysstat (psutil) | Prometheus |
|---------|------------|------------------|------------|
| **Ponto de Coleta** | Kernel (Ring 0) | Userspace (Ring 3) | Userspace (Ring 3) |
| **Mecanismo** | Kprobes dinâmicos | Polling /proc | Polling / Scrape |
| **Latência** | Medição via hooks | RTT de rede (UDP) | RTT de rede (UDP) |
| **Overhead** | Mínimo (Event-driven) | Médio (Polling) | Médio (Polling + HTTP) |
| **Requisito** | Privilégios/Headers | Padrão | Runtime Prometheus |

---

## Fluxo de Coleta

1. O **Gerador de Tráfego** inicia o envio de ataques simulados ao WAF.
2. Cada **Coletor** sonda o Servidor de Telemetria a cada 1 segundo.
3. O eBPF registra os timestamps no kernel no momento exato em que o pacote de monitoramento cruza a camada de socket.
4. Os dados são acumulados por 240 segundos.
5. O `compare.py` consolida as médias e desvios padrão para gerar a comparação final.
