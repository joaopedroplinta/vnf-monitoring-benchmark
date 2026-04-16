# TCC — Gerenciamento e Monitoramento de Rede
**Relatório do Projeto** | Gerado em: 16/04/2026

---

## Objetivo

Projeto de TCC que compara 3 abordagens de monitoramento de rede aplicadas a uma VNF (Web Application Firewall):

| Abordagem | Mecanismo |
|-----------|-----------|
| **eBPF (BCC)** | Instrumentação em nível de kernel via kprobes |
| **Sysstat** | Polling tradicional em userspace via `/proc` |
| **Prometheus** | Mesma coleta do sysstat + exposição HTTP de métricas |

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── probe.py                   # Probe UDP único (configurado por env vars)
│   ├── vnf/
│   │   ├── waf.py                 # WAF TCP porta 8080
│   │   ├── monitor_ebpf.py        # Monitor eBPF: kprobes sport=8080 + psutil
│   │   ├── monitor_sysstat.py     # Monitor sysstat: /proc/net/dev + psutil
│   │   └── monitor_prometheus.py  # Monitor Prometheus: /proc/net/dev + psutil + HTTP :8000
│   ├── client/
│   │   ├── client.py              # Envia NUM_MESSAGES mensagens TCP
│   │   └── gen_payload.py         # Gera payload.bin (60% limpo + 40% malicioso)
│   └── compare.py                 # Consolida resultados em CSV e JSON
├── configs/
│   ├── Dockerfile                 # Ubuntu 24.04 + BCC tools + Python 3
│   └── Dockerfile.client          # Python 3.9 slim
├── docker-compose.ebpf.yml        # Stack isolada eBPF
├── docker-compose.sysstat.yml     # Stack isolada Sysstat
├── docker-compose.prometheus.yml  # Stack isolada Prometheus
├── scripts/
│   ├── run_ebpf.sh                # Executa benchmark eBPF completo
│   ├── run_sysstat.sh             # Executa benchmark Sysstat completo
│   └── run_prometheus.sh          # Executa benchmark Prometheus completo
└── results/
    ├── ebpf_results.json
    ├── sysstat_results.json
    ├── prometheus_results.json
    ├── comparison.csv
    └── comparison.json
```

---

## Componentes Implementados

### 1. VNF — Web Application Firewall (`src/vnf/`)

- **`waf.py`** (85 linhas): TCP server na porta 8080
  - Detecta: SQLi, XSS, Path Traversal, RCE, Null Byte
  - Bloqueia ou encaminha requisições; não escreve métricas

- **`monitor_ebpf.py`** (113 linhas): monitor eBPF
  - Kprobes em `tcp_sendmsg` e `tcp_cleanup_rbuf`, filtro `sport=8080`
  - Coleta bytes RX/TX + CPU/mem do WAF via psutil
  - Responde a probes UDP na porta 9999 com JSON de métricas

- **`monitor_sysstat.py`** (83 linhas): monitor sysstat
  - Lê `/proc/net/dev` (interface `lo`)
  - Coleta CPU/mem do WAF via psutil
  - Responde a probes UDP na porta 9999

- **`monitor_prometheus.py`** (100 linhas): monitor Prometheus
  - Mesma lógica do sysstat
  - Expõe Gauges adicionais em `:8000/metrics` via `prometheus_client`

### 2. Probe (`src/probe.py` — 115 linhas)

- Script único compartilhado pelos três stacks
- Aguarda o monitor estar pronto (`wait_ready`) antes de iniciar a medição
- Envia requisição UDP ao monitor-server a cada 1s
- Mede RTT (roundtrip time) como métrica principal de overhead
- Configurável via variáveis de ambiente: `NUM_MESSAGES`, `DURATION`
- Saída: `results/<ferramenta>_results.json`

### 3. Geração de Tráfego (`src/client/`)

- **`client.py`** (115 linhas): envia `NUM_MESSAGES` mensagens TCP ao WAF
- **`gen_payload.py`** (75 linhas): gera `payload.bin` com seed fixa para reprodutibilidade:
  - 60% conteúdo limpo (texto, números, pontuação aleatórios)
  - 40% padrões maliciosos: SQLi, XSS, RCE, Path Traversal, Null Byte

### 4. Comparação (`src/compare.py` — 76 linhas)

- Consolida saídas dos 3 monitores
- Gera `results/comparison.csv` e `results/comparison.json`

---

## Infraestrutura Docker

Três stacks independentes com topologia idêntica:

```
Cliente TCP → WAF (porta 8080) → Monitor-server (UDP :9999)
                                         ↑
                                  probe.py (1 req/s)
```

| Stack | Configuração |
|-------|-------------|
| eBPF | `privileged: true`, `pid: host`, BPF filesystem mounts |
| sysstat / Prometheus | unprivileged, `/proc` montado read-only, `pid: host` |

Variáveis de ambiente: `NUM_MESSAGES` (padrão 100), `DURATION` (padrão = `NUM_MESSAGES`)

---

## Resultados Mais Recentes (16/04/2026 — ~100s, 100 mensagens)

| Métrica | eBPF | Sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | 0.4361 | 0.4510 | **0.3779** ✓ |
| Desvio padrão (ms) | **0.0293** ✓ | 0.0603 | 0.0923 |
| Latência mín (ms) | 0.2814 | 0.2464 | **0.2261** ✓ |
| Latência máx (ms) | **0.5032** ✓ | 0.6338 | 0.6418 |
| Amostras coletadas | **100** ✓ | **100** ✓ | **100** ✓ |
| Bytes RX | 89 338 | 160 987 | 159 173 |
| Bytes TX | 1 202 † | 160 987 | 159 173 |
| CPU média WAF (%) | 0.05 | **0.04** ✓ | 0.05 |
| Memória média WAF (MB) | 11.47 | **11.37** ✓ | 11.47 |
| Duração (s) | 100.08 | 100.08 | 100.07 |

> ✓ Melhor valor na métrica
> † eBPF mede apenas o lado servidor (`sport=8080`), resultando em TX menor

### Observações

- Após a correção do `wait_ready`, os três coletores atingem **100 amostras** e latências médias comparáveis (~0.38–0.45ms), evidenciando que as diferenças anteriores eram artefato de startup e não overhead real de monitoramento.
- **eBPF** destaca-se pela menor variância (stddev 0.03ms, máx 0.50ms) — comportamento mais previsível e estável sob carga.
- **sysstat** e **Prometheus** apresentam stddev ligeiramente maior (0.06ms e 0.09ms), reflexo do polling userspace que pode sofrer jitter de scheduler.
- **Correção aplicada:** `probe.py` aguarda prontidão do monitor (`wait_ready`) antes de iniciar o timer, eliminando perda de amostras no startup do BPF (~9s de compilação JIT do kernel) e o spike de latência na primeira amostra.

---

## Estado Atual

- Branch: `dev/joao`, limpa e atualizada com `main`
- Arquitetura: `probe.py` único + monitor por variante
- Correção: `wait_ready()` em `probe.py` garante 100 amostras para todos os coletores
- Resultados: gerados e validados (100 mensagens, seed fixa)
- Total de código: ~762 linhas Python em 8 arquivos
