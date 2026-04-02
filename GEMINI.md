# Contexto do Projeto: TCC Gerenciamento de Rede (eBPF vs Clássicos)

Este documento serve como guia de contexto para agentes de IA (Gemini CLI) entenderem a arquitetura, as métricas e o estado atual do projeto.

## 🎯 Objetivo do TCC
Comparar o desempenho, overhead e precisão de três métodos de monitoramento em uma **VNF (Virtual Network Function)**, especificamente um **WAF (Web Application Firewall)** simplificado.

### Ferramentas em Comparação:
1. **eBPF (BCC)**: Coleta de baixo nível diretamente no Kernel Linux.
2. **Sysstat (Tradicional)**: Coleta via polling de sistema operacional (`psutil` / `/proc`).
3. **Prometheus (Moderno)**: Exportação de métricas via HTTP (Pull Model).

---

## 🏗️ Arquitetura do Sistema

### 1. VNF (Servidor)
- **WAF (`src/vnf/waf.py`)**: Roda em **TCP 8080**. Inspeciona payloads contra SQLi, XSS, etc. Gera métricas de "negócio" (bloqueios/conexões).
- **Monitor Server (`src/vnf/monitor_server.py`)**: Roda em **UDP 9999**. Serve um JSON com as métricas internas do WAF para os coletores.

### 2. Coletores (Monitores)
- **eBPF (`src/ebpf/monitor_bcc.py`)**: 
    - **Versão Atual**: v21 (Filtragem por Porta).
    - **Mecanismo**: Usa `kprobes` em `tcp_sendmsg`, `tcp_cleanup_rbuf` e funções UDP.
    - **Diferencial**: Mede bytes RX/TX diretamente no Kernel, filtrando apenas as portas 8080 e 9999.
- **Sysstat (`src/sysstat/collector.py`)**:
    - **Mecanismo**: Lê `/proc/net/dev` para medir bytes de rede da interface `eth0`.
- **Prometheus (`src/prometheus/exporter.py`)**:
    - **Mecanismo**: Similar ao Sysstat, mas expõe métricas em **HTTP 8000** via `prometheus_client`.

---

## 📊 Definições de Métricas e Comportamento Esperado

| Métrica | Comportamento no eBPF | Comportamento no Sysstat/Prometheus |
|---------|-----------------------|------------------------------------|
| **Bytes RX/TX** | **Valor Alto**: Captura buffers reais do Kernel (TCP chunks). | **Valor Baixo**: Depende da atualização do `/proc` no Docker/WSL2. |
| **CPU %** | **Mínimo**: Processamento nativo no Kernel. | **Médio/Alto**: Overhead de interpretador Python e servidor HTTP. |
| **Latência** | **Zero (WSL2)**: Limitação de `kretprobes` no Kernel do WSL2. | **~0.4ms**: Tempo de ida e volta do socket UDP em user-space. |

---

## 🛠️ Comandos de Operação

### Executar bateria de testes:
```bash
# Para cada ferramenta (substituir TOOL por ebpf, sysstat ou prometheus)
docker compose -f docker-compose.TOOL.yml up --build -d
# Aguardar DURATION (padrão 240s, teste rápido 60s)
docker compose -f docker-compose.TOOL.yml down
```

### Gerar comparativo:
```bash
python3 src/compare.py
```

## ⚠️ Observações de Ambiente (WSL2 / Docker)
- O eBPF exige privilégios (`privileged: true`) e acesso aos headers do Kernel.
- A latência eBPF pode vir zerada devido à instabilidade de `kretprobes` em kernels de subsistemas virtuais.
- Os bytes RX/TX do eBPF serão sempre maiores que os outros, pois o eBPF "vê" o tráfego antes da fragmentação/agregação do SO.

---
*Este arquivo deve ser atualizado sempre que houver mudanças na lógica de filtragem ou na versão dos coletores.*
