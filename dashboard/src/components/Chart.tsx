import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { Config, Data, Layout } from "plotly.js";

// O Plotly pesa mais de 1 MB: carrega só quando o primeiro gráfico aparece.
const Plot = lazy(async () => {
  const [{ default: Plotly }, { default: createPlotlyComponent }] = await Promise.all([
    import("plotly.js-cartesian-dist-min"),
    import("react-plotly.js/factory"),
  ]);
  return { default: createPlotlyComponent(Plotly) };
});

interface Props {
  data: Data[];
  dark: boolean;
  height?: number;
  legend?: boolean;
  layout?: Partial<Layout>;
  label: string;
}

export function Chart({ data, dark, height = 310, legend = true, layout = {}, label }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState<number | undefined>(undefined);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => {
      if (el.clientWidth > 0) setWidth(el.clientWidth);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const compact = width !== undefined && width < 520;
  const muted = dark ? "#a2b1c6" : "#52647c";
  const grid = dark ? "#243349" : "#dbe3ee";

  // No desktop: permite selecionar área com o mouse para dar zoom (dragmode: "zoom") e mostra a barra ao passar o mouse.
  // No celular (compact): desativa o dragmode por arraste para não travar a rolagem da tela no touch.
  const config: Partial<Config> = {
    displayModeBar: compact ? false : "hover",
    displaylogo: false,
    scrollZoom: false,
    responsive: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
    toImageButtonOptions: { format: "png", scale: 2, filename: "grafico_vnf" },
  };

  const axis = {
    automargin: true,
    color: muted,
    gridcolor: grid,
    zeroline: false,
    linecolor: grid,
    fixedrange: compact,
    tickfont: { size: compact ? 10 : 11 },
  };

  const merged: Partial<Layout> = {
    width,
    height,
    dragmode: compact ? false : "zoom",
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    separators: ",.",
    font: { family: "Manrope, sans-serif", size: compact ? 10.5 : 12, color: muted },
    margin: { l: compact ? 4 : 10, r: compact ? 6 : 12, t: legend ? (compact ? 48 : 34) : 16, b: 10 },
    showlegend: legend,
    legend: {
      orientation: "h",
      y: compact ? 1.2 : 1.15,
      x: 0,
      font: { size: compact ? 10 : 11, color: muted },
    },
    hoverlabel: { font: { size: 12 } },
    bargap: compact ? 0.22 : 0.28,
    bargroupgap: compact ? 0.05 : 0.08,
    ...layout,
    xaxis: { ...axis, showgrid: false, ...layout.xaxis },
    yaxis: { ...axis, ...layout.yaxis },
  };

  return (
    <div ref={ref} role="img" aria-label={label} className="w-full min-w-0 overflow-hidden" style={{ minHeight: height }}>
      <Suspense fallback={<div className="animate-pulse rounded-lg bg-track/50" style={{ height }} />}>
        {width ? (
          <Plot data={data} layout={merged} config={config} style={{ width: "100%", height }} />
        ) : (
          <div className="animate-pulse rounded-lg bg-track/50" style={{ height }} />
        )}
      </Suspense>
    </div>
  );
}
