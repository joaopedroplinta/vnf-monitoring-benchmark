import { useState } from "react";
import { COLOR, Tool, confidenceSeparated, meanByTool, number } from "../lib/analytics";
import { rankTraces, trendTraces } from "../lib/charts";
import { Chart } from "../components/Chart";
import { Card, Dot, SectionTitle, Toggle } from "../components/ui";
import type { TabProps } from "./types";

export function Overview({ view, tools, log, dark }: TabProps) {
  const [noDocker, setNoDocker] = useState(false);
  const rtt = meanByTool(view, "rtt_ms");
  const memory = meanByTool(view, "mem_obs_mb");
  const inspectMs = meanByTool(view, "inspect_avg_ms");
  const [best, bestValue] = rtt[0];
  const maxRtt = Math.max(...rtt.map(([, v]) => v));
  const count = (t: Tool) => view.filter((r) => r.Ferramenta === t).length;
  const [runner, runnerValue] = rtt[1] ?? [];
  const canFocus = tools.includes("Docker") && tools.length > 1;
  const focus = noDocker && canFocus;
  const trendTools = focus ? tools.filter((t) => t !== "Docker") : tools;

  return (
    <div className="grid gap-4 xl:grid-cols-[1.7fr_1fr]">
      <Card>
        <div className="mb-1 flex flex-wrap items-start justify-between gap-3">
          <SectionTitle title="A resposta muda com a carga?" sub="RTT médio do observador por volume nominal · média ± IC95%" tag="Menor é melhor" />
          <Toggle checked={focus} onChange={setNoDocker} label="Detalhar sem Docker" disabled={!canFocus} />
        </div>
        <Chart
          label="Gráfico de linhas do RTT médio por volume e ferramenta"
          dark={dark}
          height={305}
          data={trendTraces(view, "rtt_ms", trendTools)}
          layout={{ yaxis: { type: log ? "log" : "linear", rangemode: "tozero", title: { text: "RTT médio (ms)", font: { size: 11 } } } }}
        />
      </Card>

      <Card>
        <SectionTitle title="Tempo de resposta por ferramenta" sub="Média das execuções nos volumes selecionados" tag="Menor é melhor" />
        <ul className="flex flex-col gap-4">
          {rtt.map(([tool, value]) => (
            <li key={tool}>
              <div className="flex items-baseline justify-between">
                <span className="inline-flex items-center gap-2 text-sm"><Dot tool={tool} />{tool}</span>
                <strong className="text-lg">{number(value, 3)} <small className="text-xs font-normal text-muted">ms</small></strong>
              </div>
              <div className="my-1.5 h-1.5 overflow-hidden rounded-full bg-track">
                <div className="h-full rounded-full" style={{ width: `${(value / maxRtt) * 100}%`, background: COLOR[tool] }} />
              </div>
              <div className="flex justify-between text-xs text-muted">
                <span className={tool === best ? "font-semibold text-accent" : ""}>
                  {tool === best ? "Menor média neste recorte" : `${number(value / bestValue, 2)}× o tempo de ${best}`}
                </span>
                <span>{number(count(tool))} exec.</span>
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-muted">Este resumo combina volumes. Consulte os intervalos por volume no gráfico ao lado.</p>
      </Card>

      <Card>
        <SectionTitle title="Memória para observar o WAF" sub="Consumo médio do observador nos volumes selecionados" tag="Menor é melhor" />
        <Chart
          label="Gráfico de barras da memória média do observador por ferramenta"
          dark={dark}
          height={240}
          legend={false}
          data={rankTraces(memory, "MB")}
          layout={{
            xaxis: { range: [0, Math.max(...memory.map(([, v]) => v)) * 1.3], title: { text: "Memória média (MB)", font: { size: 11 } } },
            yaxis: { autorange: "reversed" },
          }}
        />
      </Card>

      <Card>
        <SectionTitle title="O que este recorte mostra" sub="Conclusões calculadas a partir dos filtros atuais" />
        {runner ? (
          <>
            <p className="text-lg font-bold leading-snug">{best} tem RTT médio {number((1 - bestValue / runnerValue) * 100, 1)}% menor.</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">Em relação a {runner}, a segunda menor média entre as ferramentas selecionadas.</p>
            <div className="mt-4 border-t border-line pt-4">
              <h3 className="text-[13px] font-semibold">Leitura dos intervalos</h3>
              <p className="mt-1 text-[13px] leading-relaxed text-muted">
                {confidenceSeparated(view, best, runner)
                  ? `Os IC95% de ${best} e ${runner} não se sobrepõem em nenhum volume selecionado.`
                  : "A separação dos IC95% não se confirma em todos os volumes selecionados. Consulte a análise por volume."}
              </p>
            </div>
          </>
        ) : (
          <>
            <p className="text-lg font-bold">{best}, em detalhe.</p>
            <p className="mt-1.5 text-[13px] text-muted">Selecione outra ferramenta para comparar os tempos de resposta.</p>
          </>
        )}
        {memory[0] && (
          <div className="mt-4 border-t border-line pt-4">
            <h3 className="text-[13px] font-semibold">Menor consumo de memória do observador</h3>
            <p className="mt-1 text-[13px] text-muted">{memory[0][0]}: {number(memory[0][1], 2)} MB em média neste recorte.</p>
          </div>
        )}
        {inspectMs.length > 0 && (
          <div className="mt-4 border-t border-line pt-4">
            <h3 className="text-[13px] font-semibold">Validação funcional do WAF</h3>
            <p className="mt-1 text-[13px] text-muted">
              Tempo médio por inspeção entre {number(inspectMs[0][1], 4)} ms e {number(inspectMs[inspectMs.length - 1][1], 4)} ms — motor de regras estável sob todos os observadores.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
