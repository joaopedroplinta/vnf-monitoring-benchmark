# GUIA RÁPIDO — cola de bolso (Defesa Final TCC)

> Olhe de relance. Cada linha = um slide. **Negrito = número/palavra que NÃO pode esquecer.**
> Tempo total ≈ 20 min (20 slides).

| # | Slide | Tempo | Gatilhos (o que falar) |
|---|-------|-------|------------------------|
| 1 | Capa | 0:45 | João Pedro + Rafael + orientador Guilherme. "Comparamos **4 ferramentas** de monitoramento em uma VNF (WAF) para medir qual cobra menor custo." |
| 2 | Roteiro | 0:45 | Mapa dos 8 blocos. Frase-âncora: **"monitorar uma VNF tem custo — qual ferramenta cobra menos?"** |
| 3 | Contexto NFV | 1:15 | NFV = rede vira software (VNF, ex.: WAF). MANO precisa de métricas. **Monitor roda CO-LOCALIZADO, disputando CPU e RAM com a VNF.** |
| 4 | Problema e Hipótese | 1:15 | Coletor pesado degrada a VNF. Pergunta c/ as **4 ferramentas** → **Hipótese: eBPF (kernel) vence** `/proc` (Sysstat/Prometheus) e `cgroups` via daemon (Docker). |
| 5 | Objetivos | 0:45 | Geral: tempo de resposta + sobrecarga nas 4. Específicos: literatura, **4 coletores**, **4 cargas (100k–2M)**, trade-offs. |
| 6 | As 4 abordagens | 1:45 | 1. **eBPF** (`libbpf`+CO-RE, kprobes, mapa `ARRAY` no kernel). 2. **Sysstat** (`/proc/net/dev` + `psutil`). 3. **Prometheus** (Sysstat + HTTP `:8000`). 4. **Docker** (`stats(one_shot=True)` via socket → `dockerd` lê cgroups v2). |
| 7 | Lacuna na literatura | 1:00 | Cassagnes (eBPF vs polling), Casalicchio/Wiedner (Docker/cgroups), Dinga (Prometheus), Oliveira (Sysstat/MANO). **1º benchmark comparando as 4 juntas na mesma VNF.** |
| 8 | Metodologia e Ambiente | 1:00 | Aplicada, quantitativa, comparativa, experimental. **WAF** (SQLi, XSS, Path Traversal, RCE, Null Byte) intensivo em CPU. Ryzen 5 5500, Ubuntu 26.04 **modo texto**, **Kernel 7.0.0-38**. |
| 9 | Arquitetura (C4) | 1:00 | Cliente (200 corrotinas, TCP `:8080`) → WAF (`waf_metrics.json` atômico) → Observador (UDP `:9999`) ← **`probe.py` (1 req/s, mede RTT UDP em ns)**. |
| 10 | Protocolo de testes | 1:15 | $N = 100\text{k}, 500\text{k}, 1\text{M}, 2\text{M}$ (`seed=42`, fila assíncrona). **30 repetições × 4 × 4 = 480 execuções oficiais.** Média ± IC95% ($t$ de Student). Dashboard online. |
| 11 | **Tempo de resposta (RTT)** ⭐ | 1:45 | **eBPF vence em TODOS os volumes (~0,50 ms)**, IC95% sem sobreposição: **−13% vs. Sysstat (~0,57 ms)**, **−15% vs. Prometheus (~0,58 ms)** e **−80% (~5× menor) vs. Docker (~2,50 ms)**. |
| 12 | Boxplot + Custo Docker | 1:15 | Faixas separadas e desvio-padrão baixo (**1–2% da média**). **Por que Docker leva ~2,5 ms?** Cadeia síncrona: SDK → socket Unix → `dockerd` → cgroup → JSON (ler cgroup direto custa `0,04 ms`, API custa `1,4–1,7 ms`). |
| 13 | CPU do WAF (Controle) | 0:50 | Satura em **~104–110%** a partir de 500k em todos; inspeção fixa em **0,080 ms**. **Nenhum coletor interfere no WAF.** |
| 14 | CPU do Observador | 0:50 | Médias baixas (`0,05%` a `5,05%`), mas **IC95% largos → inconclusiva quantitativamente** (granularidade do `psutil` em 1s + contenção; no Docker o `dockerd` roda fora). |
| 15 | Memória do Observador | 1:00 | Constante com $N$: **Sysstat 13,6 MB** (menor) < **eBPF 15,0 MB** (`libbpf` reduziu 92% vs. BCC) < **Prometheus 24,7 MB** (+81%, HTTP) < **Docker 30,8 MB** (+126%, SDK). |
| 16 | Sensibilidade e Coleta 100% | 1:15 | Coleta oficial (1 proc.) processa 62–88% de $N \ge 500\text{k}$. Com **4 proc. WAF + 4 proc. cliente + leitura direta (+480 execuções)**: **100% de $N$ inspecionado** e **mesma ordem**: eBPF (`0,90 ms`) < Sysstat (`1,01 ms`) < Prometheus (`1,04 ms`) < Docker (`2,65 ms`). |
| 17 | Síntese comparativa | 1:00 | Tabela 4 do TCC: eBPF ganha em RTT; Sysstat em RAM; Prometheus paga pelo HTTP; Docker isola sem `pid:host`, mas paga 5× no RTT. |
| 18 | Conclusões | 1:00 | **✅ Hipótese confirmada no RTT.** Ganho sobre `/proc` é real porém moderado (`0,07–0,09 ms` vs. complexidade do eBPF). Abstração do `dockerd` custa caro. **960 execuções totais.** |
| 19 | Limitações e Futuros | 0:45 | Limites: loopback, IPC síncrono do Docker, cgroup vs. RSS, CPU observador ruidosa, Prometheus sem scraping. Futuro: **ler `/sys/fs/cgroup/` direto**, WAF single-process mais rápido, impacto fim a fim, SFC/XDP. |
| 20 | Obrigado | 0:25 | Código no GitHub + Dashboard (`vnf-lab.up.railway.app`). Aberto à banca! |

---

## Números de cabeça (decore estes 7)
1. **480 execuções oficiais + 480 de sensibilidade = 960 execuções** (30 repetições por cenário)
2. **RTT médio:** eBPF **~0,50 ms** · Sysstat **~0,57 ms** · Prometheus **~0,58 ms** · Docker **~2,50 ms**
3. **Vantagem do eBPF no RTT:** **−13%** vs. Sysstat, **−15%** vs. Prometheus, **−80% (~5×)** vs. Docker
4. **Memória do observador:** Sysstat **13,6 MB** · eBPF **15,0 MB** · Prometheus **24,7 MB** · Docker **30,8 MB**
5. **Microbenchmark Docker:** ler cgroup direto = **0,04 ms** vs. API `stats(one_shot=True)` = **1,4–1,7 ms** (~30×)
6. **Controle do WAF:** CPU satura em **~105–109%** e tempo de inspeção = **0,080 ms** nas 4 ferramentas
7. **Coleta 100% (4 processos + leitura direta):** inspeciona **100% de N** e preserva a ordem (**0,90 < 1,01 < 1,04 < 2,65 ms**)
