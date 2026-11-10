# GUIA RÁPIDO — cola de bolso (Defesa Final TCC)

> Olhe de relance. Cada linha = um slide. **Negrito = número/palavra que NÃO pode esquecer.**
> Tempo total ≈ 20 min (21 slides).

| # | Slide | Tempo | Gatilhos (o que falar) |
|---|-------|-------|------------------------|
| 1 | Capa | 0:45 | João Pedro + Rafael + orientador Guilherme. "Comparamos **4 ferramentas** de monitoramento em uma VNF (WAF) para medir qual cobra menor custo." |
| 2 | Roteiro | 0:30 | Mapa dos 8 blocos, sem enrolar. |
| 3 | Contexto NFV | 1:15 | NFV = rede vira software (VNF: firewall, IDS/IPS, balanceador, UPF 5G, WAF). **MANO = Management and Orchestration (ETSI)**: instancia, escala, migra e recupera VNFs. **A literatura mostra que o monitoramento pode sobrecarregar a VNF** (monitor CO-LOCALIZADO, disputa CPU e RAM). |
| 4 | Problema e Hipótese | 1:00 | Pergunta com as **4 ferramentas** → **Hipótese: eBPF (kernel) vence** `/proc` (Sysstat/Prometheus) e `cgroups` via daemon (Docker). A lacuna fica no slide 7. |
| 5 | Objetivos | 0:45 | Geral: tempo de resposta + sobrecarga nas 4. Específicos: literatura, **4 coletores**, **4 cargas (100k–2M)**, trade-offs. |
| 6 | As 4 abordagens | 1:00 | **Fala curta:** eBPF lê contador pronto no kernel; Sysstat lê `/proc`; Prometheus = Sysstat + servidor HTTP; Docker pergunta ao daemon, que lê os cgroups. "Ou lê pronto, ou lê arquivo, ou pede a um intermediário." |
| 7 | Trabalhos relacionados e lacuna | 1:00 | Cassagnes (eBPF vs polling), Casalicchio/Wiedner (Docker/cgroups), Dinga (Prometheus), Oliveira (Sysstat/MANO). **Lacuna: ninguém compara as 4 na mesma VNF com carga crescente e rigor estatístico.** |
| 8 | Metodologia e Ambiente | 0:50 | Aplicada, quantitativa, comparativa, experimental. **WAF** (gasta CPU). **Fala geral:** "testes em **uma máquina física**, modo texto, uma pilha Docker por ferramenta", sem listar o hardware (só se perguntarem). |
| 9 | Arquitetura (C4) | 1:00 | Cliente (200 corrotinas, TCP `:8080`) → WAF (`waf_metrics.json` atômico) → Observador (UDP `:9999`) ← **`probe.py` (1 req/s, mede RTT UDP em ns)**. |
| 10 | Protocolo de testes | 1:15 | $N = 100\text{k}, 500\text{k}, 1\text{M}, 2\text{M}$ (`seed=42`). **Janela = ⌊N/15000⌋ + 20 s** (15 mil = taxa nominal; 20 s = margem p/ subir/encerrar containers). **30 repetições × 4 × 4 = 480.** IC95% com **t de Student (só temos o desvio da amostra, não da população)**. |
| 11 | Dashboard | 0:30 | Dados abertos: React, filtros, IC95%, execuções e download. QR code no slide. |
| 12 | **Tempo de resposta (RTT)** ⭐ | 1:45 | **eBPF vence em TODOS os volumes (~0,50 ms)**, IC95% sem sobreposição: **−13% vs. Sysstat (~0,57 ms)**, **−15% vs. Prometheus (~0,58 ms)** e **−80% (~5× menor) vs. Docker (~2,50 ms)**. |
| 13 | Boxplot + Custo Docker | 1:15 | Faixas separadas e desvio-padrão baixo (**1–2% da média**). **Por que Docker leva ~2,5 ms?** Cadeia síncrona: SDK → socket Unix → `dockerd` → cgroup → JSON (ler cgroup direto custa `0,04 ms`, API custa `1,4–1,7 ms`). |
| 14 | CPU do WAF (Controle) | 0:50 | Satura em **~104–110%** a partir de 500k em todos; inspeção fixa em **0,080 ms**. **Nenhum coletor interfere no WAF.** |
| 15 | CPU do Observador | 0:50 | Médias baixas (`0,05%` a `5,05%`), mas **IC95% largos → inconclusiva** (13 de 16 grupos com IC ≥ 50% da média; só 1 de 24 pares separado) (granularidade do `psutil` em 1s + contenção; no Docker o `dockerd` roda fora). |
| 16 | Memória do Observador | 1:00 | Constante com $N$: **Sysstat 13,6 MB** (menor) < **eBPF 15,0 MB** (`libbpf` reduziu 92% vs. BCC) < **Prometheus 24,7 MB** (+81%, HTTP) < **Docker 30,8 MB** (+126%, SDK). |
| 17 | Sensibilidade e Coleta 100% | 1:15 | **Gargalo** = o que limita a vazão (WAF com **1 proc.** + cliente). **proc.** = processos. Com **WAF e cliente em 4 proc. + leitura direta** (+480 execuções, 30 repetições por ferramenta e volume): **100% de $N$** e **mesma ordem**: eBPF (`0,90 ms`) < Sysstat (`1,01`) < Prometheus (`1,04`) < Docker (`2,65`). |
| 18 | Síntese comparativa | 1:00 | Tabela 4 do TCC: eBPF ganha em RTT; Sysstat em RAM; Prometheus paga pelo HTTP; Docker isola sem `pid:host`, mas paga 5× no RTT. |
| 19 | Conclusões | 1:00 | **✅ Hipótese confirmada no RTT.** Ganho sobre `/proc` é real porém moderado (`0,07–0,09 ms` vs. complexidade do eBPF). Abstração do `dockerd` custa caro. **960 execuções totais.** |
| 20 | Trabalhos futuros | 0:45 | **Ler `/sys/fs/cgroup/` direto**, **ambiente de produção** (rede física, volume real de pacotes), impacto fim a fim, WAF single-process mais rápido, SFC/XDP. Limitação (se perguntarem): **não temos ambientes específicos; o teste não processa o volume de produção.** |
| 21 | Obrigado | 0:25 | Código no GitHub + Dashboard (`vnf-lab.up.railway.app`). Aberto à banca! |

---

## Números de cabeça (decore estes 7)
1. **480 execuções oficiais + 480 de sensibilidade = 960 execuções** (30 repetições por cenário)
2. **RTT médio:** eBPF **~0,50 ms** · Sysstat **~0,57 ms** · Prometheus **~0,58 ms** · Docker **~2,50 ms**
3. **Vantagem do eBPF no RTT:** **−13%** vs. Sysstat, **−15%** vs. Prometheus, **−80% (~5×)** vs. Docker
4. **Memória do observador:** Sysstat **13,6 MB** · eBPF **15,0 MB** · Prometheus **24,7 MB** · Docker **30,8 MB**
5. **Microbenchmark Docker:** ler cgroup direto = **0,04 ms** vs. API `stats(one_shot=True)` = **1,4–1,7 ms** (~30×)
6. **Controle do WAF:** CPU satura em **~105–109%** e tempo de inspeção = **0,080 ms** nas 4 ferramentas
7. **Coleta 100% (4 processos + leitura direta):** inspeciona **100% de N** e preserva a ordem (**0,90 < 1,01 < 1,04 < 2,65 ms**)

---

## Respostas curtas (arguição)
- **t de Student, não Z:** a Z exige o desvio padrão da **população**; só temos o da **amostra** (30 repetições).
- **UDP e TCP:** UDP no monitoramento (protocolos de gerência de rede usam UDP, leve e sem conexão); TCP na carga do WAF (firewall usa TCP para checar a conexão).
- **Janela de 20 s:** margem para subir e encerrar os containers; o 15 mil é só taxa nominal (o real foi 7–8 mil msg/s).
- **Produção:** não temos ambientes específicos; nosso teste não processa o volume de pacotes de produção.
- **MANO:** *Management and Orchestration* (ETSI), gerencia o ciclo de vida das VNFs.
