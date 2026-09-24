# ROTEIRO COMPLETO — para dominar o conteúdo (pré-banca TCC)

**Título:** Monitoramento de Funções Virtualizadas de Redes — um estudo comparativo entre ferramentas de extração de comportamento
**Duração-alvo:** ~20 min de fala + ~5 min de perguntas.

Cada tópico tem três partes:
- 🎯 **Objetivo do slide** — o que a banca precisa entender ao sair dele.
- 🗣️ **O que dizer** — a fala (não decore; entenda a ideia e diga com suas palavras).
- ↪️ **Transição** — a ponte para o próximo slide.

> Regra de ouro: olhe para a banca, não leia o slide. O slide é apoio, você é a explicação.

---

## SLIDE 1 — Capa · ~0:45

🎯 **Objetivo:** apresentar você, o parceiro, o orientador e dizer em uma frase do que se trata o trabalho.

🗣️ **O que dizer:**
> "Bom dia. Eu sou o João Pedro, e junto com o Rafael, sob orientação do professor Guilherme Werneck, vamos apresentar nosso TCC. Em uma frase: nós comparamos três ferramentas de monitoramento aplicadas a funções de rede virtualizadas, para descobrir qual delas impõe o menor custo ao sistema que está sendo observado."

↪️ **Transição:** "Antes dos resultados, deixem eu mostrar o caminho que vamos percorrer."

---

## SLIDE 2 — Roteiro · ~0:45

🎯 **Objetivo:** dar à banca o mapa da apresentação e plantar a pergunta central.

🗣️ **O que dizer:**
> "A apresentação tem oito partes: contexto de NFV; problema, hipótese e objetivos; as três abordagens; a lacuna na literatura; a metodologia; os resultados das 360 execuções; a síntese com as conclusões; e por fim limitações e trabalhos futuros."
> "E tudo gira em torno de uma pergunta simples: **monitorar uma VNF tem um custo — qual ferramenta cobra menos por esse custo?**"

↪️ **Transição:** "Vamos começar pelo contexto: por que monitorar isso é importante?"

---

## SLIDE 3 — Contexto: NFV · ~1:30

🎯 **Objetivo:** explicar o que é NFV/VNF e plantar a ideia-chave de que o monitor compete por recursos com a VNF. Esse é o gancho de todo o trabalho.

🗣️ **O que dizer:**
> "A virtualização de funções de rede, ou NFV, é a ideia de tirar as funções de rede do hardware dedicado e transformá-las em software. Em vez de um equipamento físico de firewall, você tem um programa rodando num servidor comum — isso é uma VNF. Exemplos: firewall, IDS, balanceador de carga, ou, no nosso caso, um WAF, que é um firewall de aplicação web."
> "Mas essa flexibilidade depende de monitoramento o tempo todo: o orquestrador, o MANO, precisa saber CPU, memória e tráfego para decidir quando criar mais réplicas ou recuperar uma VNF que falhou."
> "E aqui está o ponto que move todo o trabalho: nesse ambiente, **o monitor não é um agente externo — ele roda no mesmo host, lado a lado com a VNF, disputando os mesmos núcleos de CPU e a mesma memória.** Ou seja, a coleta de métricas vira concorrente do próprio serviço."

💡 *Se perguntarem o que é MANO:* é o bloco de gerência e orquestração do padrão ETSI; é quem usa as métricas para automatizar escalonamento e recuperação.

↪️ **Transição:** "E é exatamente daí que nasce o problema."

---

## SLIDE 4 — Problema, hipótese e lacuna · ~1:30

🎯 **Objetivo:** fechar o "porquê" do trabalho: o custo do monitoramento, a pergunta de pesquisa, a aposta (hipótese) e o buraco na literatura.

🗣️ **O que dizer:**
> "O problema é direto: a ferramenta de monitoramento consome recursos que deveriam ir para a VNF. Um coletor pesado acaba degradando justamente o serviço que ele deveria só observar."
> "Daí a pergunta de pesquisa: quais são as diferenças práticas de desempenho entre eBPF, Sysstat e Prometheus ao monitorar uma VNF, e qual oferece a menor sobrecarga sem comprometer a coleta?"
> "Nossa hipótese é que o eBPF, por trabalhar dentro do kernel, leva vantagem — menor tempo de resposta e menor impacto — frente ao Sysstat e ao Prometheus, que fazem polling no espaço de usuário lendo o /proc."
> "E por que estudar isso? Porque existe muito trabalho sobre eBPF sozinho, mas falta uma comparação quantitativa e controlada das três abordagens sobre uma mesma VNF, nas mesmas condições."

↪️ **Transição:** "Com o problema posto, estes são os objetivos concretos."

---

## SLIDE 5 — Objetivos · ~1:00

🎯 **Objetivo:** mostrar que o trabalho tem metas claras e mensuráveis (importante para a banca avaliar se foram cumpridas).

🗣️ **O que dizer:**
> "O objetivo geral é compreender como essas três tecnologias influenciam o tempo de resposta e a sobrecarga ao monitorar uma VNF sob diferentes cargas."
> "E os específicos, que são o que de fato fizemos: levantamos a literatura de monitoramento em NFV; implementamos os três coletores para um WAF; rodamos experimentos com quatro cargas diferentes medindo tempo de extração, CPU e memória; e analisamos as vantagens e limitações de cada abordagem."

↪️ **Transição:** "Vamos então conhecer as três ferramentas que estão no centro da comparação."

---

## SLIDE 6 — As três abordagens · ~1:45

🎯 **Objetivo:** que a banca entenda *tecnicamente* a diferença fundamental — kernel vs. espaço de usuário. É o conceito que explica todos os resultados depois.

🗣️ **O que dizer:**
> "O eBPF trabalha no nível de kernel. A gente anexa kprobes — que são ganchos dinâmicos — nas funções internas tcp_sendmsg e tcp_cleanup_rbuf, que são chamadas a cada envio e recepção de dados TCP. O eBPF conta os bytes ali dentro do kernel, guarda em mapas BPF, e o programa no espaço de usuário só lê o valor já somado. Não há cópia de pacote nem varredura de arquivo."
> "O Sysstat é a abordagem clássica de espaço de usuário: a cada requisição, ele abre o arquivo /proc/net/dev, lê, faz o parsing do texto e consulta o psutil para CPU e memória. É uma ferramenta consolidada e muito portável."
> "O Prometheus usa exatamente a mesma lógica do Sysstat, mas adiciona um servidor HTTP na porta 8000 que expõe as métricas no formato padrão dele, para integração com um coletor externo."
> "Então o contraste central, que vale a pena guardar, é este: **ler contadores já prontos no kernel, contra fazer polling de arquivos do /proc no espaço de usuário.** Tudo o que vem depois é consequência disso."

💡 *Se perguntarem o que é kprobe:* é um mecanismo do Linux que permite "grudar" um trecho de código na entrada de uma função do kernel sem recompilar o kernel.

↪️ **Transição:** "Agora, alguém já comparou as três assim? Foi o que fomos verificar na literatura."

---

## SLIDE 7 — Lacuna na literatura · ~1:15

🎯 **Objetivo:** justificar a originalidade do trabalho com a tabela — mostrar que ninguém fez a comparação das três juntas.

🗣️ **O que dizer:**
> "Quando olhamos os trabalhos relacionados, encontramos vários ângulos: o Cassagnes compara eBPF com polling, mas sem Prometheus; o Sathyaseelan e o Shahinfar estudam o eBPF isolado; o trabalho do próprio professor Oliveira, de 2026, analisa só o Sysstat."
> "Mas, como mostra a última coluna da tabela, **nenhum deles compara as três abordagens juntas, sobre uma mesma VNF, com cargas crescentes e controladas.** É essa lacuna que o nosso trabalho preenche: eBPF, Sysstat e Prometheus, no mesmo WAF, de 100 mil a 2 milhões de mensagens."

↪️ **Transição:** "Então vou mostrar como montamos esse experimento."

---

## SLIDE 8 — Metodologia · ~1:15

🎯 **Objetivo:** classificar a pesquisa e justificar por que o WAF é a VNF certa para o teste.

🗣️ **O que dizer:**
> "Metodologicamente, é uma pesquisa aplicada, quantitativa, comparativa e experimental."
> "Escolhemos um WAF como VNF representativa por um motivo específico: o WAF concentra carga de CPU na inspeção de conteúdo — ele procura SQLi, XSS, path traversal, RCE e null byte em cada mensagem. Por ser intensivo em CPU, qualquer sobrecarga extra do coletor fica visível. Se usássemos uma VNF leve, a diferença entre as ferramentas se perderia no ruído."
> "O ambiente foi um Ryzen 5 5500, 16 GB de RAM, Ubuntu 26.04. Cada ferramenta roda numa pilha Docker Compose isolada, com cliente, WAF e observador em contêineres separados."

↪️ **Transição:** "Essa é a topologia em detalhe."

---

## SLIDE 9 — Arquitetura · ~1:15

🎯 **Objetivo:** que a banca visualize o fluxo e entenda como a métrica principal é medida.

🗣️ **O que dizer:**
> "O cliente envia cargas pré-geradas para o WAF, por TCP na porta 8080, usando 200 corrotinas assíncronas com conexões persistentes. O WAF inspeciona cada mensagem e responde ALLOWED ou BLOCKED."
> "O observador é o coletor — é o único elemento que muda entre os experimentos. Ele mantém um socket UDP na porta 9999."
> "E o instrumento de medida é o probe.py: ele manda um pacote UDP por segundo para o observador e mede o tempo de ida e volta dessa resposta. **Esse RTT é a nossa métrica principal de sobrecarga** — quanto mais ocupado o coletor estiver coletando, mais demora para responder o probe."

↪️ **Transição:** "Agora, como rodamos isso de forma justa e estatisticamente válida?"

---

## SLIDE 10 — Protocolo de testes · ~1:30

🎯 **Objetivo:** mostrar rigor: cargas idênticas, repetições, e análise estatística. É o que dá credibilidade aos resultados.

🗣️ **O que dizer:**
> "A variável independente é o volume de mensagens, em quatro níveis: 100 mil, 500 mil, 1 milhão e 2 milhões."
> "A carga tem 60% de mensagens benignas e 40% maliciosas, geradas com uma semente fixa. Isso é importante: significa que a sequência exata de mensagens é idêntica para as três ferramentas. É o que garante que estamos comparando maçã com maçã."
> "Para cada combinação de coletor e volume, rodamos 30 repetições. Três coletores, quatro volumes, trinta vezes: **360 execuções no total.**"
> "A métrica primária é o RTT UDP. As secundárias são CPU e memória, do WAF e do coletor. Tudo é agregado em média com intervalo de confiança de 95%, usando a distribuição t de Student — então quando eu disser que uma diferença é significativa, é porque os intervalos não se sobrepõem."

💡 *Por que 30?* Definido com o orientador; é suficiente para usar a distribuição t e ter boa estimativa do intervalo de confiança.

↪️ **Transição:** "Com tudo montado, vamos aos resultados — começando pela métrica que mais importa."

---

## SLIDE 11 — Tempo de resposta (RESULTADO PRINCIPAL) · ~1:45 ⭐

🎯 **Objetivo:** este é o coração do trabalho. A banca tem que sair daqui convencida de que o eBPF venceu e que isso é estatisticamente sólido.

🗣️ **O que dizer:**
> "Esta é a métrica principal, o tempo de resposta do observador."
> "O resultado central: o **eBPF teve o menor tempo de resposta em todos os quatro volumes.** A redução foi de 8 a 15% em relação ao Sysstat, e de 11 a 14% em relação ao Prometheus."
> "E o mais importante para a validade: **os intervalos de confiança de 95% do eBPF nunca se sobrepõem aos das outras duas ferramentas.** Ou seja, essa vantagem é estatisticamente significativa — não é sorte nem ruído de medição."
> "E isso bate exatamente com a teoria do slide 6: o eBPF só lê um contador que já está pronto no kernel, enquanto os outros dois, a cada requisição, precisam abrir e fazer parsing do /proc no espaço de usuário."

💡 *(Se sobrar tempo, comente a curva não-monotônica:)* "Um detalhe interessante: o tempo não cresce sempre com a carga. Os menores valores estão nos volumes intermediários, porque nas execuções mais curtas a fase de aquecimento pesa mais na média."

↪️ **Transição:** "Mas a média não conta tudo — vamos ver a distribuição."

---

## SLIDE 12 — Boxplot · ~1:00

🎯 **Objetivo:** reforçar a separação eBPF vs. resto, mas com honestidade científica sobre a maior dispersão do eBPF.

🗣️ **O que dizer:**
> "O boxplot mostra a distribuição das execuções. Em 500 mil e 1 milhão, a caixa do eBPF fica inteiramente abaixo das outras duas, sem nenhuma sobreposição — confirma visualmente a separação."
> "Mas sendo honesto com os dados: o eBPF também tem maior dispersão. As caixas dele são mais largas e há alguns outliers, como aquele pico de 1,06 ms em 2 milhões. Mesmo assim, o caso típico do eBPF continua competitivo com a mediana das outras ferramentas."

↪️ **Transição:** "Esse era o desempenho. E o consumo de recursos? Começando pela CPU do WAF."

---

## SLIDE 13 — CPU do WAF (controle) · ~1:00

🎯 **Objetivo:** provar que o coletor não interfere na VNF — esse é um resultado de *controle* que valida o método.

🗣️ **O que dizer:**
> "A CPU do WAF aqui funciona como controle. A partir de 500 mil mensagens, o WAF satura em torno de 107 a 109% de uma thread — passa de 100% porque usa mais de um núcleo lógico. E o ponto é: esse valor é igual nos três casos, com os intervalos de confiança sobrepostos."
> "Isso confirma que nenhum coletor interfere no processamento do WAF. Cada abordagem afeta a própria sobrecarga, mas não a CPU da VNF — que é o esperado, já que nenhum deles entra no caminho de inspeção das requisições."

↪️ **Transição:** "Onde as ferramentas realmente se separam é na memória do próprio coletor."

---

## SLIDE 14 — Memória do observador · ~1:00

🎯 **Objetivo:** mostrar a dimensão em que há a maior diferença, e atribuir a causa (HTTP do Prometheus).

🗣️ **O que dizer:**
> "Aqui aparece a separação mais nítida entre as três. O Sysstat é o mais leve, com cerca de 14 MB. O eBPF fica logo acima, com 15. E o Prometheus salta para 24 MB — isso é 78% a mais que o Sysstat."
> "Essa diferença vem direto do servidor HTTP e da biblioteca prometheus_client, que ficam o tempo todo em memória. E reparem que o consumo é praticamente constante entre os volumes — ou seja, a memória é definida pela arquitetura da ferramenta, não pela quantidade de tráfego."

↪️ **Transição:** "E quanto à CPU do próprio coletor?"

---

## SLIDE 15 — CPU do observador · ~1:00

🎯 **Objetivo:** mostrar a vantagem mais dramática do eBPF (1–2 ordens de grandeza), mas explicar por que tratamos como qualitativa.

🗣️ **O que dizer:**
> "A CPU do próprio observador foi a métrica mais difícil de medir, mas em 100 mil mensagens o resultado é bem limpo: o eBPF consumiu 0,05% de CPU, contra 2,4% do Prometheus e 4,7% do Sysstat. Isso é uma a duas ordens de grandeza menor."
> "E faz total sentido: ler um mapa do kernel é muito mais barato que ler e fazer parsing de arquivos do /proc o tempo todo."
> "Nos volumes maiores essa métrica fica ruidosa — por causa da granularidade do psutil e da disputa de CPU entre os contêineres — então a tratamos como evidência qualitativa, não como número exato."

↪️ **Transição:** "Juntando tudo numa tabela só."

---

## SLIDE 16 — Síntese · ~1:15

🎯 **Objetivo:** consolidar todos os resultados e dar a leitura prática (não há vencedor absoluto).

🗣️ **O que dizer:**
> "Resumindo: o eBPF vence no tempo de resposta e na CPU do coletor. A CPU do WAF é equivalente nos três, como vimos. Na memória, o Sysstat é o mais leve e o Prometheus o mais pesado."
> "A leitura prática que tiramos disso é que não existe um vencedor absoluto. O eBPF é o melhor em desempenho; o Sysstat é a opção mais enxuta em memória; e o Prometheus paga um custo de memória que só compensa quando você de fato usa o ecossistema dele, com um servidor central fazendo scraping."

↪️ **Transição:** "Isso nos leva às conclusões."

---

## SLIDE 17 — Conclusões · ~1:15

🎯 **Objetivo:** responder explicitamente à hipótese e declarar a contribuição. A banca quer ouvir "a hipótese foi confirmada".

🗣️ **O que dizer:**
> "A conclusão principal: a hipótese se confirma. O eBPF entrega o menor tempo de resposta e a menor CPU de coletor, sem sobrecarregar o WAF."
> "Mas com honestidade científica: essa vantagem no tempo de resposta, embora consistente e estatisticamente significativa, é de magnitude moderada, de 8 a 15%, e vem acompanhada de maior variabilidade. Então a escolha real depende do contexto — ambiente de borda com memória escassa, ecossistema de observabilidade já existente, e assim por diante."
> "E a contribuição do trabalho é ser, até onde levantamos, o primeiro benchmark direto das três ferramentas sobre uma mesma VNF, com código aberto e reprodutível."

↪️ **Transição:** "Por fim, os limites do que fizemos e o que vem a seguir."

---

## SLIDE 18 — Limitações e trabalhos futuros · ~1:00

🎯 **Objetivo:** mostrar maturidade — reconhecer limites antes que a banca aponte, e indicar caminhos.

🗣️ **O que dizer:**
> "Como toda pesquisa, tem limites que é importante declarar. O tráfego rodou em loopback, sem o overhead de uma placa de rede física. Os contêineres dividiram os mesmos núcleos, então pode ter havido contenção. O WAF é uma implementação simplificada em Python, não é um ModSecurity de produção. E o Prometheus rodou sem um servidor central fazendo scraping, então medimos só o exporter."
> "Para o futuro: estender para uma cadeia de serviço completa, com firewall, IDS e balanceador; medir em rede física e sob ataque DDoS real; incluir o ciclo completo de scraping do Prometheus; e explorar os hooks XDP e TC do eBPF, que são ainda mais rápidos."

↪️ **Transição:** "E é isso."

---

## SLIDE 19 — Encerramento · ~0:30

🎯 **Objetivo:** fechar com elegância e abrir para perguntas.

🗣️ **O que dizer:**
> "Todo o código está público no GitHub. Agradeço a atenção da banca e fico à disposição para as perguntas."

---

## SOMA DOS TEMPOS
0:45 + 0:45 + 1:30 + 1:30 + 1:00 + 1:45 + 1:15 + 1:15 + 1:15 + 1:30 + 1:45 + 1:00 + 1:00 + 1:00 + 1:00 + 1:15 + 1:15 + 1:00 + 0:30 ≈ **~21 min**, o que dá ~19–20 min de fala efetiva com as pausas. Se precisar cortar, sacrifique os parênteses "se sobrar tempo" dos slides 11 e 15.

---

## PERGUNTAS PROVÁVEIS DA BANCA (prepare-se)

1. **"Por que loopback e não rede física?"**
   → Para isolar o custo do coletor da variância do hardware de rede. Está declarado como limitação e proposto como trabalho futuro. A validade *comparativa* se mantém, porque as condições são idênticas para os três.

2. **"O eBPF tem mais variabilidade — isso não é um problema?"**
   → É um trade-off real, que mostramos no boxplot. O caso típico ainda é o melhor, mas se o cenário exige latência *previsível*, o Sysstat pode ser preferível. É justamente por isso que dizemos que não há vencedor absoluto.

3. **"Por que 30 repetições?"**
   → Definido com o orientador. É suficiente para aplicar a distribuição t de Student e estimar o IC95% com bom poder estatístico.

4. **"O Prometheus não foi prejudicado por não ter scraping?"**
   → Sim, e isso está declarado. Medimos só o exporter; o custo real, com scraping, seria maior. O ganho do Prometheus só aparece quando o ecossistema completo é usado.

5. **"Por que um WAF e não outra VNF?"**
   → Porque é intensivo em CPU e representativo em segurança (a literatura aponta o WAF como dos mais beneficiados por eBPF). Isso torna a sobrecarga do coletor visível.

6. **"Cinco execuções tiveram inspect_count = 0 — isso comprometeu os dados?"**
   → Não. Foi uma condição de corrida apenas na leitura do arquivo waf_metrics.json. O RTT UDP dessas execuções é válido e foi mantido — preservamos as 30 repetições da métrica primária. Só descartamos as métricas de inspeção zeradas dessas cinco.

7. **"Qual a diferença prática de 8–15%? É pouco?"**
   → Em uma VNF operando perto do limite, ou numa SFC com vários elos onde a sobrecarga se acumula, essa margem pode ser a diferença entre cumprir ou violar o SLA. Em folga de recursos, é menos crítico — por isso recomendamos decidir pelo contexto.

8. **"eBPF não exige privilégio e kernel recente? Não é uma desvantagem?"**
   → Sim, o coletor eBPF precisa de modo privilegiado e de um kernel com BTF. É um custo operacional real frente à simplicidade do Sysstat. O CO-RE com libbpf reduz isso ao permitir compilar uma vez e rodar em kernels diferentes.
