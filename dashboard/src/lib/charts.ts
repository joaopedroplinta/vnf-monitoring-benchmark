import type { Data } from "plotly.js";
import { COLOR, Metric, Row, Tool, mean, number, summary } from "./analytics";

const DASH: Record<Tool, "solid" | "dash" | "dot" | "dashdot"> = {
  eBPF: "solid", Sysstat: "dash", Prometheus: "dot", Docker: "dashdot",
};
const SYMBOL: Record<Tool, "circle" | "diamond" | "square" | "x"> = {
  eBPF: "circle", Sysstat: "diamond", Prometheus: "square", Docker: "x",
};

const orNull = (v: number) => (Number.isFinite(v) ? v : null);

/** Linhas de média ± IC95% por volume, uma por ferramenta. */
export function trendTraces(rows: Row[], metric: Metric, tools: Tool[]): Data[] {
  const s = summary(rows, metric);
  return tools.map((tool) => {
    const g = s.filter((x) => x.Ferramenta === tool);
    return {
      type: "scatter", mode: "lines+markers", name: tool,
      x: g.map((x) => x.N), y: g.map((x) => orNull(x.mean)),
      error_y: { type: "data", array: g.map((x) => orNull(x.ci)), visible: true, thickness: 1.1, width: 3 },
      line: { color: COLOR[tool], width: 2.5, dash: DASH[tool] },
      marker: { color: COLOR[tool], size: 8, symbol: SYMBOL[tool] },
      customdata: g.map((x) => [x.count, x.ci]),
      hovertemplate: "%{x}<br>%{y:.3f} ms ± %{customdata[1]:.3f}<br>%{customdata[0]} execuções<extra>%{fullData.name}</extra>",
    } as Data;
  });
}

/** Barras agrupadas de média ± IC95% por volume. */
export function barTraces(rows: Row[], tools: Tool[]): (metric: Metric) => Data[] {
  return (metric) => {
    const s = summary(rows, metric);
    return tools.map((tool) => {
      const g = s.filter((x) => x.Ferramenta === tool);
      return {
        type: "bar", name: tool,
        x: g.map((x) => x.N), y: g.map((x) => orNull(x.mean)),
        marker: { color: COLOR[tool], line: { width: 0 } },
        error_y: { type: "data", array: g.map((x) => orNull(x.ci)), visible: true, thickness: 1.2, width: 3 },
        customdata: g.map((x) => [x.count, x.ci]),
        hovertemplate: "%{x}<br>Média: %{y:.3f}<br>IC95%: ±%{customdata[1]:.3f}<br>%{customdata[0]} execuções<extra>%{fullData.name}</extra>",
      } as Data;
    });
  };
}

/** Barras horizontais de uma média por ferramenta. */
export function rankTraces(values: [Tool, number][], unit: string): Data[] {
  return [{
    type: "bar", orientation: "h",
    y: values.map(([t]) => t), x: values.map(([, v]) => v),
    marker: { color: values.map(([t]) => COLOR[t]) },
    text: values.map(([, v]) => `${number(v, 2)} ${unit}`),
    textposition: "outside", cliponaxis: false, width: 0.48,
    hovertemplate: "%{y}<br>%{x:.3f} " + unit + "<extra></extra>",
  } as Data];
}

/** Caixas com todos os pontos: cada ponto é uma execução. */
export function boxTraces(rows: Row[], tools: Tool[]): Data[] {
  const sorted = [...rows].sort((a, b) => a.n - b.n);
  return tools.map((tool) => {
    const g = sorted.filter((r) => r.Ferramenta === tool);
    return {
      type: "box", name: tool, x: g.map((r) => r.N), y: g.map((r) => r.rtt_ms),
      boxpoints: "all", jitter: 0.25, pointpos: 0,
      marker: { color: COLOR[tool], size: 3 }, line: { color: COLOR[tool] },
    } as Data;
  });
}

/** Valor de uma métrica em cada execução de um volume, na ordem de repetição, opcionalmente com linha de média. */
export function runTraces(rows: Row[], tools: Tool[], metric: Metric = "rtt_ms", showMean = false): Data[] {
  const traces: Data[] = [];
  for (const tool of tools) {
    const g = rows.filter((r) => r.Ferramenta === tool).sort((a, b) => a.run - b.run);
    traces.push({
      type: "scatter", mode: "lines+markers", name: tool,
      x: g.map((r) => r.run), y: g.map((r) => orNull(r[metric])),
      line: { color: COLOR[tool], width: 1.8, dash: DASH[tool] },
      marker: { color: COLOR[tool], size: 5, symbol: SYMBOL[tool] },
      hovertemplate: "Execução %{x}<br>%{y:.3f}<extra>%{fullData.name}</extra>",
    } as Data);
    if (showMean && g.length > 1) {
      const m = mean(g.map((r) => r[metric]));
      if (Number.isFinite(m)) {
        traces.push({
          type: "scatter", mode: "lines", name: `${tool} (média)`,
          x: [g[0].run, g[g.length - 1].run], y: [m, m],
          line: { color: COLOR[tool], width: 1.2, dash: "dot" },
          showlegend: false,
          hoverinfo: "skip",
        } as Data);
      }
    }
  }
  return traces;
}
