# ROTEIRO COMPLETO — para dominar o conteúdo (Defesa Final do TCC)

**Título:** Monitoramento de Funções Virtualizadas de Redes: um estudo comparativo entre ferramentas de extração de comportamento
**Duração-alvo:** ~20 min de fala (21 slides) + arguição da banca.

Cada tópico tem três partes:
- 🎯 **Objetivo do slide** — o que a banca precisa entender ao sair dele.
- 🗣️ **O que dizer** — a fala (não decore palavra por palavra; entenda a lógica e fale com naturalidade).
- ↪️ **Transição** — a ponte para o próximo slide.

> Regra de ouro: olhe para a banca, não leia o slide. O slide é apoio visual; você é a explicação.

---

## SLIDE 1 — Capa · ~0:45

🎯 **Objetivo:** apresentar você, o Rafael, o orientador e resumir o TCC em uma frase direta.

🗣️ **O que dizer:**
> "Bom dia / Boa tarde a todos. Eu sou o João Pedro, e junto com o Rafael, sob orientação do professor Guilherme Werneck, vamos apresentar a defesa final do nosso TCC. Em uma frase: nós comparamos quatro abordagens de monitoramento aplicadas a uma função de rede virtualizada — eBPF, Sysstat, Prometheus e a API do Docker — para medir qual delas impõe a menor sobrecarga ao ambiente monitorado."

↪️ **Transição:** "Antes de entrar nos dados, deixem eu mostrar o roteiro que vamos percorrer."

---

## SLIDE 2 — Roteiro da apresentação · ~0:30

🎯 **Objetivo:** dar à banca o mapa dos 8 blocos, sem enrolar.

🗣️ **O que dizer:**
> "A apresentação está organizada em oito partes: o contexto de NFV; o problema, a hipótese e os objetivos; as quatro abordagens avaliadas; os trabalhos relacionados e a lacuna de pesquisa; a metodologia e a arquitetura experimental; os resultados das 480 execuções oficiais; a análise de sensibilidade da vazão, com mais 480 execuções; e por fim a síntese, as conclusões e os trabalhos futuros."

↪️ **Transição:** "Vamos começar pelo contexto: por que monitorar funções virtualizadas é tão sensível?"

---

## SLIDE 3 — Contexto: Virtualização de Funções de Rede (NFV) · ~1:15

🎯 **Objetivo:** explicar NFV, VNF e MANO com exemplos técnicos, e mostrar que o monitor roda junto da VNF.

🗣️ **O que dizer:**
> "A Virtualização de Funções de Rede, a NFV, tira os serviços de rede de equipamentos dedicados e passa a rodá-los como software, em servidores comuns. Cada função assim é uma VNF. Exemplos técnicos: firewall, IDS/IPS (detecção e prevenção de intrusão), balanceador de carga, a UPF do núcleo 5G (que encaminha o tráfego dos usuários) e, no nosso caso, um WAF, o Firewall de Aplicação Web."
> "Essas funções precisam ser escaladas, migradas ou recuperadas conforme a demanda. Quem decide isso é o **MANO — Management and Orchestration**, a camada de gerência e orquestração da arquitetura NFV definida pelo ETSI. Ele cuida do ciclo de vida das VNFs (instanciar, escalar, migrar, recuperar) e, para decidir, precisa de métricas de CPU, memória, vazão e latência. Se a métrica chega atrasada, o orquestrador reage tarde e pode violar o SLA."
> "E aqui está o ponto-chave: **a literatura mostra que o monitoramento pode sobrecarregar a VNF**, porque o observador roda co-localizado à VNF, no mesmo host, disputando os mesmos núcleos de CPU e a mesma memória."

↪️ **Transição:** "É daí que vêm o nosso problema de pesquisa e a nossa hipótese."

---

## SLIDE 4 — Problema de pesquisa e hipótese · ~1:00

🎯 **Objetivo:** apresentar a questão de pesquisa com as 4 ferramentas e a hipótese (kernel vs. espaço de usuário). A lacuna fica para o slide 7.

🗣️ **O que dizer:**
> "Nossa questão de pesquisa é: **quais são as diferenças práticas de desempenho entre o eBPF, o Sysstat, o Prometheus e a API do Docker no monitoramento de uma VNF, e qual oferece menor sobrecarga?**"
> "Nossa hipótese é que o **eBPF**, por operar no nível do *kernel* via *kprobes*, apresenta menor tempo de resposta e menor sobrecarga que as três abordagens em espaço de usuário: o Sysstat e o Prometheus, que fazem *polling* lendo e interpretando arquivos do `/proc`, e a API do Docker, que consulta os *cgroups* por meio do *daemon* `dockerd`."

↪️ **Transição:** "Com o problema e a hipótese definidos, estes foram os nossos objetivos."

---

## SLIDE 5 — Objetivos · ~0:45

🎯 **Objetivo:** mostrar metas claras e verificáveis que foram integralmente cumpridas na versão final do trabalho.

🗣️ **O que dizer:**
> "O objetivo geral foi compreender como eBPF, Sysstat, Prometheus e a API do Docker influenciam o tempo de resposta de extração de métricas e a sobrecarga no monitoramento de uma VNF sob diferentes condições de consumo."
> "E nos objetivos específicos: analisamos a literatura de monitoramento em NFV; implementamos os quatro coletores para monitorar um WAF; executamos experimentos quantitativos em quatro volumes de carga — de 100 mil a 2 milhões de mensagens — medindo tempo de resposta, CPU e memória; e analisamos as vantagens, limitações e *trade-offs* de cada abordagem."

↪️ **Transição:** "Vamos entender agora como cada uma das quatro abordagens coleta os dados na prática."

---

## SLIDE 6 — As quatro abordagens comparadas · ~1:00

🎯 **Objetivo:** dar a ideia de cada abordagem em uma frase. O slide fica como está; a simplificação é só na fala.

🗣️ **O que dizer (versão curta):**
> "São quatro formas de coletar as métricas. O **eBPF** roda dentro do kernel e lê um contador que o próprio kernel já soma. O **Sysstat** faz polling: a cada consulta, lê e interpreta arquivos do `/proc`. O **Prometheus** faz a mesma coleta do Sysstat e ainda mantém um servidor HTTP ativo para expor as métricas. E o **Docker** pergunta ao daemon do Docker, que lê os cgroups e devolve o resultado."
> "Resumindo: ou se lê um contador pronto no kernel, ou se lê arquivo, ou se pede para um intermediário."

🧠 **Se perguntarem o detalhe:** eBPF usa `libbpf` com CO-RE e kprobes em `tcp_sendmsg` e `tcp_cleanup_rbuf` (porta 8080), somando os bytes num mapa `ARRAY`; Sysstat usa `/proc/net/dev` e `psutil`; Prometheus acrescenta o endpoint `/metrics` na porta 8000; Docker usa `container.stats(one_shot=True)` pelo socket Unix, e quem lê os cgroups v2 é o `dockerd`.

↪️ **Transição:** "Mas o que a literatura já havia medido sobre isso?"

---

## SLIDE 7 — Trabalhos relacionados e lacuna · ~1:00

🎯 **Objetivo:** situar o trabalho frente à literatura e trazer a lacuna de pesquisa.

🗣️ **O que dizer:**
> "A literatura cobre partes do problema: Cassagnes et al. comparam eBPF com *polling*, mas sem Prometheus nem Docker; Casalicchio e Wiedner estudam o desempenho do Docker e dos *cgroups*; Dinga et al. avaliam o Prometheus em microsserviços; Kannan e Shahinfar focam só no eBPF; e Oliveira et al. avaliam o impacto da latência de coleta do Sysstat na orquestração."
> "**A lacuna é que nenhum desses trabalhos compara as quatro abordagens sobre a mesma VNF, com carga crescente e rigor estatístico.** É isso que este trabalho faz."

↪️ **Transição:** "Vou mostrar agora a metodologia que construímos para fazer essa comparação de forma justa."

---

## SLIDE 8 — Metodologia e ambiente experimental · ~0:50

🎯 **Objetivo:** justificar o WAF e dizer onde foi testado, sem listar o ambiente. O slide fica como está; a fala é geral.

🗣️ **O que dizer:**
> "É uma pesquisa aplicada, quantitativa, comparativa e experimental. Como VNF, usamos um WAF em Python que inspeciona ataques como SQL injection e XSS. Escolhemos um WAF porque inspecionar conteúdo gasta bastante CPU, então qualquer sobrecarga do coletor aparece."
> "Os testes rodaram em uma única máquina física, em modo texto, para reduzir processos concorrentes durante as medições. Cada ferramenta teve a sua própria pilha de containers Docker, com as versões das bibliotecas fixadas."

🧠 **Se perguntarem o hardware:** AMD Ryzen 5 5500, 6 núcleos e 12 threads, 16 GB de RAM, Ubuntu 26.04, kernel 7.0.0-38, Docker Engine 29.8.2.

↪️ **Transição:** "No próximo slide temos o diagrama C4 dessa topologia."

---

## SLIDE 9 — Arquitetura experimental (Diagrama C4 — Nível 2) · ~1:00

🎯 **Objetivo:** explicar o fluxo entre Cliente, WAF, Observador e Probe (`probe.py`).

🗣️ **O que dizer:**
> "A topologia tem quatro componentes:"
> "1. O **Cliente** abre 200 corrotinas assíncronas com conexões TCP persistentes para a porta 8080 do WAF, enviando mensagens com prefixo de 4 bytes."
> "2. O **WAF** inspeciona cada carga, responde `ALLOWED` ou `BLOCKED`, e a cada 100 requisições persiste as estatísticas de inspeção em `waf_metrics.json` usando gravação atômica."
> "3. O **Observador** é o contêiner que muda entre as quatro pilhas — eBPF, Sysstat, Prometheus ou Docker. Ele escuta na porta UDP 9999."
> "4. E o **Probe (`probe.py`)** é o nosso instrumento de medição: ele envia uma requisição UDP por segundo ao observador e mede o tempo de ida e volta com resolução de nanossegundos (`time.time_ns()`). **Esse RTT UDP é a nossa métrica primária**, pois mede diretamente quanto tempo cada ferramenta leva para coletar e entregar as métricas."

↪️ **Transição:** "E como garantimos a validade estatística das medições?"

---

## SLIDE 10 — Protocolo de testes e rigor estatístico · ~1:15

🎯 **Objetivo:** destacar a carga determinística, a janela de coleta, as 480 execuções e o IC95% com t de Student.

🗣️ **O que dizer:**
> "Avaliamos quatro volumes de mensagens: 100 mil, 500 mil, 1 milhão e 2 milhões. As cargas têm 60% de mensagens benignas e 40% maliciosas, embaralhadas com semente fixa `42`, então as quatro ferramentas enfrentam exatamente a mesma sequência."
> "A **janela de coleta** é `DURATION = ⌊N / 15000⌋ + 20` segundos, ou seja, 26, 53, 86 e 153 s. O 15 mil é uma **taxa nominal** de mensagens por segundo, usada só para dimensionar o tempo; os 20 segundos são **margem** para subir e encerrar os containers."
> "Para cada uma das 16 combinações de ferramenta e volume, fizemos **30 repetições independentes**: 480 execuções oficiais. Reportamos a média com **intervalo de confiança de 95% pela distribuição t de Student**."

🧠 **Por que t de Student e não a tabela Z?** A tabela Z exige conhecer o desvio padrão da **população**. Nós só temos o desvio padrão da **amostra** (as 30 repetições), então usamos a t de Student, que corrige essa incerteza (29 graus de liberdade, t ≈ 2,045). Com amostra grande a diferença para a Z é pequena, mas a t é a escolha correta aqui.

🧠 **Por que 20 s de margem?** O coletor sobe e desce junto com os containers, e a janela precisa cobrir o envio todo. Na prática o ambiente sustentou só ~7 a 8 mil msg/s, não 15 mil, e por isso em N ≥ 500k o WAF processou 62% a 88% das mensagens dentro da janela (ver slide 17).

↪️ **Transição:** "O dashboard permite explorar tudo isso. Em seguida, os resultados."

---

## SLIDE 11 — Dashboard interativo dos resultados · ~0:30

🎯 **Objetivo:** mostrar que os dados são abertos e reproduzíveis.

🗣️ **O que dizer:**
> "Todos os resultados estão num dashboard público, em React, onde dá para filtrar por bateria, ferramenta e volume, ver o intervalo de confiança, as execuções individuais e baixar os dados. O QR code leva direto para ele."

↪️ **Transição:** "Agora, os resultados, começando pela métrica primária."

---

## SLIDE 12 — Tempo de resposta do observador (RTT UDP) ⭐ · ~1:45

🎯 **Objetivo:** apresentar o resultado principal do TCC com clareza absoluta.

🗣️ **O que dizer:**
> "Aqui temos o resultado central do trabalho: o tempo de resposta médio do observador nos quatro volumes."
> "O **eBPF obteve o menor tempo de resposta em todos os volumes** — cerca de `0,50 ms` a partir de 500 mil mensagens. Isso representa uma redução de **12,8% a 13,4% em relação ao Sysstat** (`~0,57 ms`), de **14,4% a 14,9% em relação ao Prometheus** (`~0,58 ms`), e de **cerca de 80% — cinco vezes menor — em relação à API do Docker** (`~2,50 ms`)."
> "Em nenhum volume os intervalos de confiança de 95% do eBPF se sobrepõem aos das demais ferramentas, comprovando que a diferença é estatisticamente significativa."
> "Isso confirma na prática a diferença arquitetural: o eBPF lê contadores já prontos em memória compartilhada com o kernel, enquanto Sysstat e Prometheus fazem *parsing* de `/proc/net/dev` e `psutil` a cada requisição, e o Prometheus ainda adiciona de 1,4% a 2,1% sobre o Sysstat pelo servidor HTTP ativo."

↪️ **Transição:** "Mas como se comportam a dispersão entre as 30 execuções e por que o Docker levou 2,5 ms? É o que vemos no próximo slide."

---

## SLIDE 13 — Distribuição do RTT e o custo da API do Docker · ~1:15

🎯 **Objetivo:** mostrar os boxplots (com e sem Docker) e explicar a análise isolada das etapas do Docker (`bench_docker_cgroup.py`).

🗣️ **O que dizer:**
> "No gráfico à esquerda temos os boxplots das 30 execuções. Na linha superior estão as quatro ferramentas; como os `2,5 ms` do Docker comprimem a escala, a linha inferior faz um zoom omitindo o Docker. Vemos que a caixa do eBPF fica inteiramente abaixo de Sysstat e Prometheus em todos os volumes, e que todas as ferramentas tiveram baixíssima dispersão entre execuções — desvio-padrão de apenas 1% a 2% da média."
> "E por que o Docker leva cerca de `2,5 ms`? Porque cada sonda UDP dispara uma cadeia síncrona: o SDK Python envia uma requisição HTTP pelo socket Unix, o *daemon* `dockerd` lê os arquivos do *cgroup*, serializa toda a árvore de estatísticas do contêiner em JSON e devolve ao Python."
> "Para comprovar isso, fizemos uma análise isolada das etapas (`bench_docker_cgroup.py`): **ler os arquivos do cgroup diretamente no sistema de arquivos leva apenas `0,04 a 0,05 ms`**; um ping vazio ao daemon já custa `0,5 a 0,6 ms`; e a chamada `stats(one_shot=True)` leva de `1,4 a 1,7 ms` — cerca de 30 vezes mais que a leitura direta. Ou seja, o kernel entrega o dado rápido; o custo está na camada de IPC e serialização do daemon."

↪️ **Transição:** "Visto o tempo de resposta, vamos avaliar o impacto sobre a VNF: o consumo de CPU do WAF."

---

## SLIDE 14 — Consumo de CPU do processo WAF (Controle) · ~0:50

🎯 **Objetivo:** mostrar que o WAF satura de forma igual nos 4 coletores (~104–110%) e que nenhum coletor interfere na VNF.

🗣️ **O que dizer:**
> "O consumo de CPU do WAF atua como variável de controle. A partir de 500 mil mensagens, o WAF opera em saturação entre `104% e 110%` de um núcleo lógico nos quatro cenários — em 1 milhão, por exemplo, fica entre `105,3%` e `106,1%`. Além disso, a métrica de validação mostrou que o tempo médio de inspeção por mensagem convergiu exatamente para `0,080 ms` nas quatro ferramentas."
> "Isso confirma que nenhum dos coletores interfere de forma perceptível na capacidade de processamento do WAF."

↪️ **Transição:** "Seguindo a ordem do Capítulo 3, vejamos agora o consumo de CPU e de memória do próprio observador."

---

## SLIDE 15 — Consumo de CPU do próprio observador · ~0:50

🎯 **Objetivo:** apresentar com rigor científico por que a CPU do observador é tratada como evidência qualitativa complementar (inconclusiva quantitativamente).

🗣️ **O que dizer:**
> "Na CPU do próprio processo observador, observamos médias baixas em todos os 16 grupos — de `0,05%` a `5,05%` —, porém quase sempre acompanhadas de intervalos de confiança largos, da ordem da própria média, causados por picos isolados de escalonamento."
> "Isso ocorre pela granularidade da amostragem do `psutil` em intervalos curtos de 1 segundo e pela disputa de núcleos entre os contêineres. Além disso, no caso do Docker, quem faz a leitura do *cgroup* é o processo externo `dockerd`, cujo consumo de CPU não entra na conta do observador. Por honestidade científica, tratamos essa métrica como inconclusiva quantitativamente."

🧠 **Como provar que é inconclusiva:** em **13 dos 16 grupos** o IC95% é maior ou igual a **50% da própria média** (o desvio padrão chega a 5 vezes a média). Entre as ferramentas, só **1 de 24 pares** ficou separado (eBPF vs. Prometheus em 500k, com médias de 0,05% e 0,06%, uma diferença sem importância prática). Ou seja: não dá para ordenar as ferramentas por CPU do observador.

↪️ **Transição:** "Já no consumo de memória do observador, a separação entre as quatro arquiteturas é nítida e altamente estável."

---

## SLIDE 16 — Consumo de memória do observador e do WAF · ~1:00

🎯 **Objetivo:** destacar a diferença de footprint de memória do observador (13,6 vs. 15,0 vs. 24,7 vs. 30,8 MB) e a ressalva do cgroup vs. RSS na memória do WAF.

🗣️ **O que dizer:**
> "A memória do observador representa o custo fixo de manter a ferramenta ativa, e permanece constante em todos os volumes com intervalos de confiança inferiores a `0,06 MB`:"
> "• O **Sysstat** foi o mais enxuto, com `13,6 MB`;"
> "• O **eBPF** ficou muito próximo, com `15,0 MB` — vale destacar que a nossa migração do antigo arcabouço BCC/LLVM para `libbpf + CO-RE` reduziu a memória do eBPF em 92%, caindo de `~196 MB` para `15 MB`;"
> "• O **Prometheus** consumiu `24,7 MB` (+81% que o Sysstat), reflexo direto do servidor HTTP e da biblioteca `prometheus_client`;"
> "• E o **Docker** consumiu `30,8 MB` (+126% que o Sysstat), devido ao SDK Python do Docker e suas dependências."
> "Sobre a memória do WAF: no eBPF, Sysstat e Prometheus ela cresce igualmente de `28 MB` a `46 MB` (medida como RSS pelo `psutil`). No Docker os números aparecem ~6 a 8 MB menores porque o *cgroup* contabiliza `usage − inactive_file` e não RSS — portanto são grandezas distintas e não comparáveis."

↪️ **Transição:** "Durante a análise das métricas de validação, notamos um ponto importante sobre a vazão do WAF nos volumes maiores, que motivou uma investigação adicional."

---

## SLIDE 17 — Análise de sensibilidade da vazão e coleta com 100% de N · ~1:15

🎯 **Objetivo:** explicar o que é o gargalo e por que repetimos a bateria. Mostrar maturidade experimental: explicar por que a coleta oficial inspecionou 62–88% de N nos volumes maiores e mostrar a bateria extra de 480 execuções que atingiu 100% de N mantendo a mesma conclusão.

🧠 **Palavras-chave:** **gargalo** = o ponto que limita a vazão (aqui, o WAF com 1 processo e o cliente lendo os payloads). **proc.** = processos do sistema operacional (`WAF_PROCESSES` e `CLIENT_PROCESSES`). **Repetições** = as 30 execuções independentes de cada combinação de ferramenta e volume. **Leitura direta** = o cliente lê o arquivo de payloads direto no laço de eventos, sem passar pelo *thread pool* a cada mensagem.

🗣️ **O que dizer:**
> "Na coleta oficial, com 1 processo de WAF e 1 de cliente, a vazão sustentada foi de 7 a 8 mil mensagens por segundo. Com isso, dentro da janela `DURATION`, o WAF processou 100% das 100 mil mensagens, mas de 62% a 88% nos volumes de 500 mil a 2 milhões. Embora a carga processada tenha sido idêntica entre as 4 ferramentas, investigamos a causa desse teto."
> "Na Tabela à esquerda, variando a configuração no eBPF em $N = 1$ milhão, descobrimos dois gargalos simultâneos: o processo único do WAF e o uso do *pool* de *threads* a cada leitura no cliente. Quando combinamos **4 processos de WAF, 4 de cliente e leitura direta no laço de eventos**, o WAF inspecionou **100% das mensagens**."
> "Repetimos então a bateria inteira nessa configuração — **mais 480 execuções** (Tabela à direita). Em todas as 16 combinações o WAF inspecionou 100% de $N$, e **a ordem entre as ferramentas se manteve inalterada em todos os volumes**: eBPF (`~0,90 ms`) < Sysstat (`~1,01 ms`) < Prometheus (`~1,04 ms`) < Docker (`~2,65 ms`). O acréscimo de `~0,4 ms` nos três primeiros ocorre porque o `psutil` passa a consultar 4 processos `waf.py` por sonda em vez de 1. Isso prova que a conclusão do trabalho independe de o WAF processar a fração ou a totalidade de $N$."

↪️ **Transição:** "Consolidando todas as dimensões analisadas, chegamos à tabela de síntese."

---

## SLIDE 18 — Síntese comparativa das quatro abordagens · ~1:00

🎯 **Objetivo:** resumir a Tabela 4 do TCC e apontar quando cada ferramenta é indicada.

🗣️ **O que dizer:**
> "Em síntese: o **eBPF** vence na métrica primária de tempo de resposta em todos os cenários e tem memória baixa (`15 MB`), exigindo em contrapartida modo privilegiado, BTF e `pid:host`."
> "O **Sysstat** tem o menor consumo de memória (`13,6 MB`), não exige privilégio de kernel e fica apenas `~0,07 ms` atrás do eBPF."
> "O **Prometheus** tem tempo próximo ao Sysstat, mas paga `+11 MB` de RAM pelo servidor HTTP — custo que só se justifica quando integrado a um servidor Prometheus fazendo coleta ativa."
> "E a **API do Docker** tem a vantagem operacional de dispensar `pid:host` e expor métricas por contêiner, mas cobra um tempo de resposta cinco vezes maior (`~2,5 ms`) e o maior consumo de memória (`30,8 MB`)."

↪️ **Transição:** "Isso nos leva às conclusões gerais do trabalho."

---

## SLIDE 19 — Conclusões · ~1:00

🎯 **Objetivo:** responder diretamente à hipótese e destacar as contribuições concretas do TCC.

🗣️ **O que dizer:**
> "Concluímos que **a hipótese inicial foi confirmada para a métrica primária**: por operar no kernel, o eBPF entrega o menor tempo de resposta em todos os volumes (**−13% vs. Sysstat, −15% vs. Prometheus e −80% vs. Docker**), sem impor sobrecarga adicional à CPU do WAF."
> "Em termos práticos, mostramos que o ganho do eBPF sobre o *polling* de `/proc` é real e estatisticamente significativo, porém moderado em termos absolutos (`0,07 a 0,09 ms`), devendo ser ponderado frente à maior complexidade de implementação e privilégios de kernel. Já a comparação com a API do Docker demonstrou empiricamente como camadas intermediárias de IPC e serialização (`dockerd`) elevam em 30 vezes o custo de acessar métricas que o próprio kernel mantém nos *cgroups*."
> "Como contribuições concretas, entregamos um benchmark de código aberto totalmente reprodutível com **960 execuções**, a implementação eBPF enxuta com `libbpf + CO-RE`, e o dashboard interativo público."

↪️ **Transição:** "Para finalizar, destacamos as limitações do estudo e os trabalhos futuros."

---

## SLIDE 20 — Trabalhos futuros · ~0:45

🎯 **Objetivo:** apontar os próximos passos. As limitações saem do slide e entram na fala e nas respostas.

🗣️ **O que dizer:**
> "Como trabalhos futuros: **(i)** coletar os dados dos cgroups v2 direto de `/sys/fs/cgroup/`, sem passar pelo `dockerd`, para isolar o custo da API do Docker; **(ii)** repetir o experimento em rede física e com o volume de pacotes de um ambiente de produção, não só em loopback; **(iii)** medir o impacto do monitoramento na latência e na vazão das requisições dos clientes do WAF; **(iv)** avaliar um WAF de alta vazão em processo único; e **(v)** estender para cadeias de VNFs, Prometheus com scraping ativo e hooks XDP/TC."

🧠 **Se perguntarem sobre limitações:** não temos ambientes específicos. Acreditamos que o nosso ambiente de teste não processa a quantidade de pacotes que um ambiente de produção processa. O tráfego também é em loopback, e o Prometheus foi avaliado só como exporter, sem scraping ativo.

↪️ **Transição:** "Com isso encerramos a nossa apresentação."

---

## SLIDE 21 — Encerramento · ~0:25

🎯 **Objetivo:** agradecer à banca e deixar os links visíveis.

🗣️ **O que dizer:**
> "Todo o código-fonte, os dados brutos das execuções e o painel interativo estão abertos nos links da tela. Muito obrigado pela atenção da banca, e estamos à disposição para as perguntas e considerações."

---

## PERGUNTAS PROVÁVEIS DA BANCA (Defesa Final)

1. **"Por que o coletor Docker ficou tão mais lento (~2,5 ms) se o cgroup também está no kernel?"**
   → Porque o observador não lê o arquivo do *cgroup* diretamente; ele usa o SDK oficial do Docker (`container.stats(stream=False, one_shot=True)`), que faz uma requisição HTTP sobre o socket Unix `/var/run/docker.sock` até o *daemon* `dockerd` (em Go). O `dockerd` lê vários arquivos do *cgroup*, monta um JSON grande com todas as estatísticas do contêiner e serializa de volta. Na nossa análise isolada (`bench_docker_cgroup.py`), ler `cpu.stat` e `memory.current` direto do `/sys/fs/cgroup` levou apenas `0,04 ms`, enquanto passar pela API do daemon levou `1,4 a 1,7 ms`.

2. **"Por que vocês não colocaram uma thread em background ou cache no coletor Docker para responder rápido ao UDP?"**
   → Explicamos isso na Seção 3.1: se o Docker respondesse a partir de um valor em cache, o RTT mediria apenas a leitura de uma variável em memória local e entregaria uma métrica defasada, enquanto eBPF, Sysstat e Prometheus coletam a métrica fresca no exato instante da requisição UDP. Isso tornaria a comparação metodologicamente injusta.

3. **"Na primeira coleta de 480 execuções, 22% tiveram `inspect_count = 0`. Como vocês resolveram isso?"**
   → Identificamos que o WAF abria e escrevia `waf_metrics.json` diretamente; quando a sonda UDP lia o arquivo no exato instante da escrita, pegava o arquivo truncado e retornava zero. Corrigimos o WAF para fazer escrita atômica (grava em arquivo temporário e aplica `os.replace`) e **repetimos integralmente as 480 execuções**. Na bateria oficial apresentada no TCC, 0 de 480 execuções tiveram falha, e os RTTs bateram dentro do IC95% com a primeira coleta.

4. **"Por que o RTT aumentou de ~0,50 ms para ~0,90 ms no eBPF na coleta com 4 processos do WAF (Seção 3.6)?"**
   → Porque o observador eBPF (assim como Sysstat e Prometheus) usa `psutil` para consultar CPU e memória de todos os processos `waf.py` ativos a cada sonda UDP. Com 4 processos do WAF em vez de 1, o custo de varrer os processos no `/proc` via `psutil` quadruplica, somando `~0,4 ms` ao RTT dos três coletores. Já o Docker subiu apenas `~0,15 ms` (`2,50 → 2,65 ms`) porque consulta o *cgroup* do contêiner inteiro em uma única chamada. Ainda assim, a ordem `eBPF < Sysstat < Prometheus < Docker` se manteve em 100% dos volumes.

5. **"Como vocês reduziram a memória do eBPF de ~196 MB para 15 MB?"**
   → Na versão preliminar usávamos BCC (`python3-bpfcc`), que embute o compilador LLVM/Clang inteiro dentro do processo Python em tempo de execução. Migramos para `libbpf + CO-RE` (*Compile Once – Run Everywhere*): o programa C (`ebpf_kern.c`) é compilado com `clang` e `bpftool` usando o BTF do kernel antes de iniciar o Python, e o observador carrega o `.o` via `ctypes` + `libbpf.so.1`, reduzindo 92% do uso de RAM.

6. **"Por que usaram a t de Student e não a tabela Z?"**
   → Porque a Z exige conhecer o desvio padrão da população, e nós só temos o da amostra (as 30 repetições). A t de Student leva isso em conta (29 graus de liberdade, t ≈ 2,045). Com 30 amostras a diferença é pequena, mas a t é a escolha correta.

7. **"Por que usaram UDP e TCP?"**
   → São papéis diferentes. O **UDP** é o canal de monitoramento (o `probe.py` consulta o observador): em geral os protocolos de gerenciamento de rede se baseiam em UDP, por ser leve e sem conexão, e isso mede só o custo da coleta. O **TCP** é o canal da carga de trabalho (cliente para o WAF): um firewall usa TCP para checar a conexão e inspecionar o conteúdo das requisições.

8. **"Por que a janela de coleta tem 20 segundos a mais?"**
   → `DURATION = ⌊N/15000⌋ + 20`. O 15 mil é uma taxa nominal de mensagens por segundo, só para dimensionar. Os 20 s são margem para subir e encerrar os containers. Na prática o ambiente sustentou 7 a 8 mil msg/s, e por isso o WAF processou 62% a 88% de N em N ≥ 500k.

9. **"O que é o gargalo e o que são as repetições do slide 17?"**
   → Gargalo é o que limita a vazão: o WAF com 1 processo e o cliente lendo os payloads. Eliminamos isso com 4 processos de WAF, 4 de cliente e leitura direta, e repetimos a bateria inteira (mais 480 execuções, com 30 repetições por ferramenta e volume). O WAF passou a inspecionar 100% de N e a ordem entre as ferramentas se manteve.

10. **"Vocês testaram em ambiente de produção?"**
    → Não temos ambientes específicos. Acreditamos que o nosso ambiente de teste não processa a quantidade de pacotes que um ambiente de produção processa. Por isso listamos como trabalho futuro repetir o experimento em rede física e com volume de produção.

11. **"Por que a CPU do observador é inconclusiva?"**
    → Em 13 dos 16 grupos o IC95% é maior ou igual a 50% da média, e só 1 de 24 pares de ferramentas ficou separado (eBPF vs. Prometheus em 500k, com médias de 0,05% e 0,06%). A amostragem do `psutil` em 1 s e a disputa de núcleos geram picos isolados.

12. **"O que é o MANO?"**
    → *Management and Orchestration*, a camada de gerência e orquestração da arquitetura NFV (ETSI). Gerencia o ciclo de vida das VNFs: instancia, escala, migra e recupera. Para decidir, depende das métricas de monitoramento.

---

## GLOSSÁRIO — saiba explicar cada palavra

- **NFV** (*Network Functions Virtualization*): rodar funções de rede como software em servidores comuns, em vez de equipamento dedicado.
- **VNF** (*Virtualized Network Function*): uma função de rede virtualizada, como firewall, IDS ou balanceador.
- **MANO**: gerência e orquestração das VNFs (instanciar, escalar, migrar, recuperar).
- **SLA**: acordo de nível de serviço; o desempenho mínimo prometido.
- **WAF** (*Web Application Firewall*): firewall que inspeciona o conteúdo de requisições web (SQLi, XSS etc.).
- **eBPF**: código que roda dentro do kernel Linux com segurança, sem alterar o kernel.
- **kprobe**: gancho que executa um programa eBPF quando uma função do kernel é chamada (`tcp_sendmsg`, `tcp_cleanup_rbuf`).
- **libbpf + CO-RE**: biblioteca e técnica que compilam o programa eBPF uma vez e o executam em kernels diferentes (*Compile Once, Run Everywhere*).
- **BCC**: antiga forma de usar eBPF, que embute o compilador LLVM no processo; usava ~196 MB de RAM.
- **`/proc`**: sistema de arquivos virtual do Linux com estatísticas de processos e de rede.
- **psutil**: biblioteca Python que lê CPU e memória dos processos pelo `/proc`.
- **Sysstat**: família de ferramentas de coleta no espaço de usuário, por *polling* de `/proc`.
- **Prometheus / exporter / scraping**: sistema de monitoramento; o *exporter* expõe métricas por HTTP em `/metrics`; o *scraping* é o servidor Prometheus buscando essas métricas periodicamente.
- **cgroup**: recurso do kernel que limita e contabiliza CPU e memória de um grupo de processos (a base dos containers).
- **dockerd / daemon**: processo em segundo plano do Docker que gerencia os containers e responde à API.
- **IPC**: comunicação entre processos; aqui, a conversa com o `dockerd` pelo socket Unix.
- **RTT UDP**: tempo de ida e volta de uma consulta UDP; nossa métrica primária.
- **UDP vs. TCP**: UDP é leve e sem conexão; TCP é orientado a conexão e confiável.
- **Loopback (`lo`)**: interface de rede interna da máquina; o tráfego não passa por placa física.
- **IC95%**: intervalo em que a média verdadeira está com 95% de confiança.
- **t de Student**: distribuição usada quando só se conhece o desvio padrão da amostra.
- **Vazão (throughput)**: mensagens processadas por segundo.
- **SFC**: cadeia de funções de rede encadeadas.
- **XDP/TC**: pontos de gancho eBPF na camada de rede, antes da pilha TCP/IP (XDP) e no controle de tráfego (TC).
