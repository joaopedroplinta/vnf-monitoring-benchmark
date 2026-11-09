import { useState } from "react";
import { meanByTool, number, summary } from "../lib/analytics";
import { DATASETS } from "../lib/data";
import { barTraces, boxTraces } from "../lib/charts";
import { Chart } from "../components/Chart";
import { Card, Dot, SectionTitle, Toggle } from "../components/ui";
import type { TabProps } from "./types";

const DOCKER_BREAKDOWN = [
  { step: "Leitura direta de cgroup (sysfs)", time: "0,04–0,05 ms", ratio: "1× (base)", desc: "Acesso direto a memory.current, cpu.stat e /proc/<pid>/net/dev." },
  { step: "Requisição HTTP vazia (/_ping)", time: "0,50–0,60 ms", ratio: "~12×", desc: "Custo de transporte IPC via socket Unix até o daemon dockerd." },
  { step: "container.stats(one_shot=True)", time: "1,40–1,70 ms", ratio: "~34×", desc: "Coleta de subsistemas pelo daemon e serialização do payload JSON." },
  { step: "Sob carga (experimento completo)", time: "~2,50 ms", ratio: "~50×", desc: "RTT observado durante o tráfego de 100 mil a 2 M de payloads." },
];

export function Latency({ view, tools, log, dark }: TabProps) {
  const [noDockerBars, setNoDockerBars] = useState(false);
  const [noDockerBox, setNoDockerBox] = useState(false);
  const rtt = meanByTool(view, "rtt_ms");
  const [best, bestValue] = rtt[0];
  const canFocus = tools.includes("Docker") && tools.length > 1;
  const withoutDocker = (on: boolean) => (on && canFocus ? tools.filter((t) => t !== "Docker") : tools);
  const barTools = withoutDocker(noDockerBars);
  const boxTools = withoutDocker(noDockerBox);
  const type = log ? "log" : "linear";

  // Comparação direta entre a coleta oficial (1 proc.) e a inspeção integral (4 proc., 100% de N) em N = 2M
  const official2M = summary(DATASETS.oficial.rows.filter((r) => r.n === 2000000), "rtt_ms");
  const optimized2M = summary(DATASETS.otimizada.rows.filter((r) => r.n === 2000000), "rtt_ms");

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tools.map((tool) => {
          const value = rtt.find(([t]) => t === tool)?.[1] ?? NaN;
          return (
            <div key={tool} className="rounded-xl border border-line bg-surface p-3.5 sm:p-4">
              <div className="inline-flex items-center gap-2 text-[13px] text-muted"><Dot tool={tool} />{tool}</div>
              <div className="mt-1 text-xl font-extrabold tracking-tight sm:text-2xl">{number(value, 3)} <small className="text-xs font-normal text-muted">ms</small></div>
              <div className="mt-1 text-xs text-muted">{tool === best ? "Menor média no recorte" : `${number(value / bestValue, 2)}× o tempo de ${best}`}</div>
            </div>
          );
        })}
      </div>

      <Card>
        <div className="mb-1 flex flex-wrap items-start justify-between gap-3">
          <SectionTitle title="Tempo de resposta por volume" sub="Barras de erro representam o IC95% da média de cada combinação." tag="Menor é melhor" />
          <Toggle checked={noDockerBars && canFocus} onChange={setNoDockerBars} label="Detalhar sem Docker" disabled={!canFocus} />
        </div>
        <Chart
          label="Gráfico de barras do RTT por volume e ferramenta, com IC95%"
          dark={dark}
          height={380}
          data={barTraces(view, barTools)("rtt_ms")}
          layout={{ barmode: "group", yaxis: { type, title: { text: "RTT médio (ms)", font: { size: 11 } } } }}
        />
      </Card>

      <Card>
        <div className="mb-1 flex flex-wrap items-start justify-between gap-3">
          <SectionTitle title="Como as execuções se distribuem?" sub="Cada ponto representa o RTT médio de uma execução do experimento." />
          <Toggle checked={noDockerBox && canFocus} onChange={setNoDockerBox} label="Detalhar sem Docker" disabled={!canFocus} />
        </div>
        <Chart
          label="Boxplot do RTT por volume e ferramenta, com cada execução"
          dark={dark}
          height={370}
          data={boxTraces(view, boxTools)}
          layout={{ boxmode: "group", yaxis: { type, title: { text: "RTT médio da execução (ms)", font: { size: 11 } } } }}
        />
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <SectionTitle
            title="Por que a API do Docker apresenta RTT ~4,5× maior?"
            sub="Decomposição isolada das etapas de coleta em bench_docker_cgroup.py (Seção 4.2)."
          />
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr className="border-b border-line text-left text-muted">
                  <th className="py-2 pr-3 font-semibold">Etapa avaliada</th>
                  <th className="py-2 pr-3 font-semibold">Latência</th>
                  <th className="py-2 pr-3 font-semibold">Escala</th>
                  <th className="py-2 font-semibold">Causa principal</th>
                </tr>
              </thead>
              <tbody>
                {DOCKER_BREAKDOWN.map((row) => (
                  <tr key={row.step} className="border-b border-line/60 last:border-none">
                    <td className="py-2 pr-3 font-medium text-ink">{row.step}</td>
                    <td className="whitespace-nowrap py-2 pr-3 font-mono font-semibold text-accent">{row.time}</td>
                    <td className="whitespace-nowrap py-2 pr-3 text-muted">{row.ratio}</td>
                    <td className="py-2 text-muted">{row.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            O atraso de ~2,5 ms <b className="text-ink">não decorre dos cgroups do Linux</b> (cuja leitura direta em <code className="rounded bg-strip px-1 py-0.5">/sys/fs/cgroup</code> leva apenas 0,04–0,05 ms), mas da intermediação IPC/HTTP e serialização JSON do daemon <code className="rounded bg-strip px-1 py-0.5">dockerd</code>.
          </p>
        </Card>

        <Card>
          <SectionTitle
            title="Sensibilidade: Coleta Oficial vs. Inspeção Integral (N = 2 M)"
            sub="Comparação entre 1 processo WAF (62% de N inspecionado) e 4 processos WAF (100% de N inspecionado)."
          />
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr className="border-b border-line text-left text-muted">
                  <th className="py-2 pr-3 font-semibold">Ferramenta</th>
                  <th className="py-2 pr-3 font-semibold">Coleta Oficial (62% de 2 M)</th>
                  <th className="py-2 pr-3 font-semibold">Inspeção Integral (100% de 2 M)</th>
                  <th className="py-2 font-semibold">Diferença</th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool) => {
                  const off = official2M.find((g) => g.Ferramenta === tool);
                  const opt = optimized2M.find((g) => g.Ferramenta === tool);
                  const diffPct = off && opt ? ((opt.mean - off.mean) / off.mean) * 100 : 0;
                  return (
                    <tr key={tool} className="border-b border-line/60 last:border-none">
                      <td className="py-2 pr-3 font-medium text-ink">
                        <span className="inline-flex items-center gap-1.5"><Dot tool={tool} />{tool}</span>
                      </td>
                      <td className="whitespace-nowrap py-2 pr-3 tabular-nums">
                        {off ? `${number(off.mean, 4)} ± ${number(off.ci, 4)} ms` : "—"}
                      </td>
                      <td className="whitespace-nowrap py-2 pr-3 tabular-nums">
                        {opt ? `${number(opt.mean, 4)} ± ${number(opt.ci, 4)} ms` : "—"}
                      </td>
                      <td className="whitespace-nowrap py-2 tabular-nums text-muted">
                        {diffPct >= 0 ? `+${number(diffPct, 1)}%` : `${number(diffPct, 1)}%`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            Conforme a <b className="text-ink">Seção 4.6 (Tabela 4.6)</b>, o aumento de ~0,40 ms no eBPF/Sysstat/Prometheus decorre de o <code className="rounded bg-strip px-1 py-0.5">psutil</code> consultar 4 processos <code className="rounded bg-strip px-1 py-0.5">waf.py</code> a cada requisição (contra ~0,15 ms no Docker, que faz uma única chamada por contêiner). A coleta oficial permanece como resultado principal, e a coleta complementar confirma que <b className="text-ink">a ordem eBPF &lt; Sysstat &lt; Prometheus &lt; Docker se mantém com 100% de N inspecionado</b>.
          </p>
        </Card>
      </div>
    </div>
  );
}
