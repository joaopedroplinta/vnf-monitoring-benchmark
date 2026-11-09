import { SectionTitle } from "../components/ui";

const STEPS = [
  ["Cliente", "Envia payloads HTTP por TCP: 60% benignos e 40% maliciosos (SQLi e XSS)."],
  ["WAF (VNF)", "Inspeciona os payloads por expressões regulares e contabiliza bloqueios e latência."],
  ["Observador", "Coleta métricas de rede, CPU e memória com a ferramenta em teste e responde por UDP."],
  ["Probe", "Envia 1 consulta UDP por segundo e registra o RTT de resposta do observador."],
];

const APPROACH: [string, string, string][] = [
  ["eBPF", "kprobes em tcp_sendmsg e tcp_cleanup_rbuf (libbpf + CO-RE)", "Filtra apenas a porta 8080 do WAF diretamente no kernel"],
  ["Sysstat", "Leitura periódica de /proc/net/dev em espaço de usuário", "Contabiliza todo o tráfego da interface loopback (lo)"],
  ["Prometheus", "Leitura de /proc/net/dev + servidor HTTP /metrics ativo (porta 9101)", "Contabiliza a interface lo e mantém endpoint de exposição"],
  ["Docker", "API do Docker Engine via container.stats() sobre socket Unix", "Lê cgroups v2 e namespaces do contêiner via daemon dockerd"],
];

const LIMITS = [
  "Tráfego em loopback (lo), com gerador de carga, WAF e observador compartilhando a mesma máquina física.",
  "Coletas em baterias sequenciais não intercaladas: variações de escalonamento do SO podem influenciar medidas de CPU.",
  "Na Coleta Oficial (1 processo WAF), N é nominal: em 2 M de mensagens, ~62,4% dos payloads são inspecionados antes do encerramento do envio. Para isolar esse fator, uma 2ª bateria de 480 execuções com 4 processos WAF + 4 clientes foi executada (Inspeção Integral, 100% de N), confirmando a mesma ordenação de RTT.",
  "Assimetria de escopo de rede: o eBPF contabiliza apenas os bytes dos sockets na porta 8080, enquanto Sysstat, Prometheus e Docker contabilizam toda a interface loopback.",
  "Escopo de memória do WAF: na API do Docker a métrica vem de memory.current do cgroup (RSS + cache de páginas), enquanto nas demais ferramentas vem do RSS do processo via psutil.",
  "O cliente Prometheus foi avaliado como exporter local (servidor HTTP ativo), sem um servidor Prometheus externo realizando scraping concorrente.",
  "A CPU do observador apresentou alta variabilidade intragrupo e intervalos de confiança amplos, sendo tratada como inconclusiva.",
];

export function Method() {
  return (
    <div className="flex flex-col gap-5">
      <SectionTitle title="Um experimento, quatro formas de observar e duas baterias (960 execuções)" sub="O mesmo WAF e o mesmo probe UDP em todas as abordagens." />
      <ol className="grid gap-3 md:grid-cols-4">
        {STEPS.map(([name, text], i) => (
          <li key={name} className="rounded-xl border border-line bg-surface p-4">
            <span className="text-xs font-semibold text-accent">{i + 1}</span>
            <strong className="block text-[15px]">{name}</strong>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">{text}</p>
          </li>
        ))}
      </ol>
      <p className="text-sm leading-relaxed">
        O <b>RTT mede o tempo de resposta do observador</b> às consultas do probe. O consumo de CPU e memória do WAF e o tempo médio de inspeção (<code className="rounded bg-strip px-1 py-0.5">inspect_avg_ms ≈ 0,080 ms</code>) validam que a função de rede operou sob condições equivalentes.
      </p>
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="w-full text-[13px]">
          <thead className="bg-strip text-left">
            <tr>
              <th className="px-4 py-2.5">Ferramenta</th>
              <th className="px-4 py-2.5">Mecanismo de coleta</th>
              <th className="px-4 py-2.5">Escopo observado</th>
            </tr>
          </thead>
          <tbody>
            {APPROACH.map(([tool, how, scope]) => (
              <tr key={tool} className="border-t border-line">
                <td className="px-4 py-2 font-semibold">{tool}</td>
                <td className="px-4 py-2 text-muted">{how}</td>
                <td className="px-4 py-2 text-muted">{scope}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details open className="rounded-xl border border-line bg-surface px-4 py-3 text-[13px] leading-relaxed text-muted">
        <summary className="cursor-pointer font-semibold text-ink">Estatística, reprodutibilidade e leitura dos gráficos</summary>
        <p className="mt-2">
          Cada combinação de ferramenta (4) e volume (4) foi repetida <b className="text-ink">30 vezes</b>, totalizando <b className="text-ink">480 execuções na Coleta Oficial</b> e mais <b className="text-ink">480 execuções na bateria de Inspeção Integral (100% de N)</b>. Os gráficos mostram <b className="text-ink">média ± intervalo de confiança de 95%</b> (distribuição <i>t</i> de Student, 29 graus de liberdade, <i>t</i> ≈ 2,045). A ausência de sobreposição entre ICs é verificada individualmente em cada volume nominal.
        </p>
      </details>
      <details open className="rounded-xl border border-line bg-surface px-4 py-3 text-[13px] leading-relaxed text-muted">
        <summary className="cursor-pointer font-semibold text-ink">Limitações e ameaças à validade (Seção 3.9)</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">{LIMITS.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
      <p className="text-xs text-muted">João Pedro dos Santos Henrique Plinta e Rafael Correia Alves · Orientação: Prof. Guilherme Werneck de Oliveira · IFPR Campus Pinhais, 2026</p>
    </div>
  );
}
