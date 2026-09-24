# GUIA RÁPIDO — cola de bolso (pré-banca TCC)

> Olhe de relance. Cada linha = um slide. **Negrito = número/palavra que NÃO pode esquecer.**
> Tempo total ≈ 20 min. Se atrasar, corte os parênteses dos slides 11, 12 e 15.

| # | Slide | Tempo | Gatilhos (o que falar) |
|---|-------|-------|------------------------|
| 1 | Capa | 0:45 | Quem sou + Rafael + orientador Guilherme. "Comparamos 3 ferramentas de monitoramento e medimos qual custa menos." |
| 2 | Roteiro | 0:45 | Ordem da fala. Frase-âncora: **"monitorar tem custo — qual cobra menos?"** |
| 3 | Contexto NFV | 1:30 | NFV = rede vira software (VNF). Ex.: WAF. Precisa de métricas. **Monitor roda CO-LOCALIZADO, disputa CPU/RAM.** |
| 4 | Problema | 1:30 | Coletor consome recurso da VNF. Pergunta de pesquisa → **Hipótese: eBPF (kernel) ganha** → Lacuna: faltam comparações das 3. |
| 5 | Objetivos | 1:00 | Geral: tempo de resposta + sobrecarga. Específicos: literatura, 3 coletores, **4 cargas**, vantagens/limites. |
| 6 | As 3 ferramentas | 1:45 | eBPF = **kernel, kprobes, mapas BPF**. Sysstat = **/proc + psutil (polling)**. Prometheus = Sysstat **+ HTTP 8000**. Contraste: kernel vs /proc. |
| 7 | Lacuna | 1:15 | Tabela: outros comparam 1 ou 2. **Só este compara as 3 na mesma VNF, 100k–2M.** |
| 8 | Metodologia | 1:15 | Aplicada/quantitativa/experimental. **WAF** (SQLi, XSS...) é intensivo em CPU → torna sobrecarga visível. Ryzen 5, Docker. |
| 9 | Arquitetura | 1:15 | Cliente→**WAF (TCP 8080)**→Observador (**UDP 9999**). **probe.py mede RTT a cada 1s** = métrica principal. |
| 10 | Protocolo | 1:30 | N = **100k/500k/1M/2M**. Carga semente fixa = idêntica. 200 corrotinas. **30 reps × 3 × 4 = 360 execuções.** Média ± IC95%. |
| 11 | **Tempo de resposta** ⭐ | 1:45 | **eBPF menor em TODOS.** **−8 a −15%.** **IC95% nunca se sobrepõem = significativo.** Lê contador pronto vs parsear /proc. |
| 12 | Boxplot | 1:00 | 500k e 1M: caixa eBPF **toda abaixo**. Contra: eBPF tem **mais dispersão** (outlier 1,06 ms). |
| 13 | CPU do WAF | 1:00 | Satura **~107–109%**, **igual nos 3** (controle). Nenhum coletor mexe no WAF. |
| 14 | Memória observador | 1:00 | Sysstat **~14 MB** < eBPF **~15** < Prometheus **~24 MB (+78%)**. Culpa do HTTP. Constante c/ volume. |
| 15 | CPU observador | 1:00 | 100k: eBPF **0,05%** vs Prometheus 2,37% vs Sysstat 4,66%. **1–2 ordens de grandeza menor.** |
| 16 | Síntese | 1:15 | eBPF ganha RTT+CPU coletor. CPU WAF igual. Sysstat memória. Prometheus mais pesado. **Sem vencedor absoluto.** |
| 17 | Conclusões | 1:15 | **✅ Hipótese confirmada.** Ganho real mas **moderado (8–15%)**. Escolha = contexto. Contribuição: 1º benchmark das 3. |
| 18 | Limitações/Futuros | 1:00 | Limites: loopback, núcleos compartilhados, WAF Python, Prometheus sem scraping. Futuro: SFC, rede física, DDoS, XDP. |
| 19 | Obrigado | 0:30 | Código no GitHub. Agradeço, abro p/ perguntas. |

---

## Números de cabeça (decore estes 6)
- **360** execuções (3 × 4 × 30)
- **−8% a −15%** = vantagem do eBPF no tempo de resposta
- **4 cargas:** 100k, 500k, 1M, 2M
- **Memória:** Sysstat 14 · eBPF 15 · Prometheus 24 MB (**+78%**)
- **CPU do coletor (100k):** eBPF 0,05% vs 2,4% vs 4,7%
- **WAF satura ~107–109%** (igual nos 3 = controle)

## Frases de transição (para emendar slides)
- "Mas isso tem um custo…" (3→4)
- "Para responder isso, precisamos de três peças…" (6→7→8)
- "Com o ambiente montado, vamos aos resultados." (10→11)
- "Esse era o desempenho; e o consumo de recursos?" (12→13)
- "Juntando tudo…" (15→16)

## Se travar
- Respire, olhe o gráfico e descreva o que ele mostra — o número está na tela.
- Frase coringa: *"o ponto central aqui é que o eBPF lê no kernel, os outros leem o /proc."*
