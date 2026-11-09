import { useState } from "react";
import { Metric, RUN_METRICS, volume } from "../lib/analytics";
import { runTraces } from "../lib/charts";
import { Chart } from "../components/Chart";
import { Card, Info, SectionTitle, Select, Toggle } from "../components/ui";
import type { TabProps } from "./types";

export function Runs({ view, tools, log, dark }: TabProps) {
  const volumes = [...new Set(view.map((r) => r.n))].sort((a, b) => a - b);
  const [picked, setPicked] = useState(volumes[0]);
  const [metric, setMetric] = useState<Metric>("rtt_ms");
  const [showMean, setShowMean] = useState(true);
  const [noDocker, setNoDocker] = useState(false);

  // O volume escolhido pode sair do recorte quando os filtros mudam.
  const n = volumes.includes(picked) ? picked : volumes[0];
  const canFocus = metric === "rtt_ms" && tools.includes("Docker") && tools.length > 1;
  const focus = noDocker && canFocus;
  const activeTools = focus ? tools.filter((t) => t !== "Docker") : tools;

  return (
    <div className="flex flex-col gap-4">
      <SectionTitle title="Da média às execuções individuais" sub="Compare a estabilidade do observador e do WAF ao longo das 30 repetições independentes de cada carga." />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap gap-4">
          <Select
            label="Volume das execuções"
            value={n}
            onChange={setPicked}
            options={volumes.map((v) => ({ value: v, label: new Intl.NumberFormat("pt-BR").format(v) }))}
          />
          <Select
            label="Métrica analisada"
            value={metric}
            onChange={setMetric}
            options={(Object.keys(RUN_METRICS) as Metric[]).map((m) => ({ value: m, label: RUN_METRICS[m] }))}
          />
        </div>
        <div className="flex flex-wrap items-center gap-4 pb-1">
          <Toggle checked={showMean} onChange={setShowMean} label="Mostrar linha da média" />
          {metric === "rtt_ms" && (
            <Toggle checked={focus} onChange={setNoDocker} label="Detalhar sem Docker" disabled={!canFocus} />
          )}
        </div>
      </div>

      {metric === "cpu_obs" && (
        <Info>
          Observe como picos pontuais em execuções isoladas elevam a média e ampliam o IC95% na análise agregada — razão pela qual a CPU do observador é tratada como inconclusiva no texto da monografia.
        </Info>
      )}
      {metric === "inspect_pct" && (
        <Info>
          Na Coleta Oficial (1 processo), a fração inspecionada cai de ~99,8% (100 mil) para ~62,4% (2 M) devido ao throughput de processo único em Python. Na bateria de Inspeção Integral (4 processos), mantém-se em 100% em todas as 30 execuções.
        </Info>
      )}

      <Card>
        <SectionTitle
          title={`${RUN_METRICS[metric]} de cada execução · ${volume(n)} mensagens`}
          sub="Os pontos são execuções independentes (1 a 30), não uma série temporal contínua. Linhas pontilhadas indicam a média do lote."
        />
        <Chart
          label={`Gráfico de linhas de ${RUN_METRICS[metric]} em cada execução com ${volume(n)} mensagens`}
          dark={dark}
          height={420}
          data={runTraces(view.filter((r) => r.n === n), activeTools, metric, showMean)}
          layout={{
            xaxis: { title: { text: "Execução (1 a 30)", font: { size: 11 } }, dtick: 5 },
            yaxis: { type: log ? "log" : "linear", title: { text: RUN_METRICS[metric], font: { size: 11 } } },
          }}
        />
      </Card>
    </div>
  );
}
