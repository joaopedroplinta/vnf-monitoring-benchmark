import raw from "../../data.csv?raw";
import rawOpt from "../../data_otimizada.csv?raw";
import { LABEL, Metric, Row, summary, Tool, volume } from "./analytics";

const NUMERIC = [
  "n", "run", "rtt_ms", "rtt_std_ms", "cpu_waf", "mem_waf_mb", "cpu_obs",
  "mem_obs_mb", "inspect_count", "inspect_avg_ms", "bytes_rx", "bytes_tx",
] as const;

/** Colunas originais do CSV, na ordem em que são exportadas. */
export const CSV_COLUMNS = ["tool", "n", "run", ...NUMERIC.slice(2)] as const;

export type DatasetId = "oficial" | "otimizada";

function parse(text: string): Row[] {
  const [header, ...lines] = text.trim().split(/\r?\n/);
  const cols = header.split(",");
  return lines.map((line) => {
    const cells = line.split(",");
    const rec: Record<string, string> = {};
    cols.forEach((c, i) => (rec[c] = cells[i]));
    const row: Record<string, unknown> = { tool: rec.tool };
    for (const k of NUMERIC) row[k] = rec[k] === "" || rec[k] === undefined ? NaN : Number(rec[k]);
    row.Ferramenta = (LABEL as Record<string, Tool>)[rec.tool] ?? rec.tool;
    row.N = volume(Number(rec.n));
    const nVal = Number(rec.n);
    const inspVal = Number(rec.inspect_count);
    row.inspect_pct = nVal > 0 && Number.isFinite(inspVal) ? (inspVal / nVal) * 100 : NaN;
    return row as unknown as Row;
  });
}

export const DATA: Row[] = parse(raw);
export const DATA_OTIMIZADA: Row[] = parse(rawOpt);

export const DATASETS: Record<DatasetId, { label: string; shortLabel: string; desc: string; rows: Row[] }> = {
  oficial: {
    label: "Coleta oficial (1 proc.)",
    shortLabel: "Coleta oficial (1 proc. WAF + 1 cliente)",
    desc: "Configuração padrão da monografia (480 execuções). Vazão de ~7–8 mil msg/s (processa 100% em 100k e 62%–88% em N ≥ 500k).",
    rows: DATA,
  },
  otimizada: {
    label: "Inspeção integral (4 proc.)",
    shortLabel: "Inspeção integral (4 proc. WAF + 4 cliente + leitura direta)",
    desc: "Análise de sensibilidade da Seção 4.6 / Tabela 4.6 (480 execuções). Inspeciona 100% de N em todos os volumes e preserva a ordem eBPF < Sysstat < Prometheus < Docker.",
    rows: DATA_OTIMIZADA,
  },
};

export const ALL_VOLUMES: number[] = [...new Set(DATA.map((r) => r.n))].sort((a, b) => a - b);

/** CSV do recorte selecionado, com as colunas originais. */
export function toCsv(rows: Row[]): string {
  const lines = [CSV_COLUMNS.join(",")];
  for (const r of [...rows].sort((a, b) => a.tool.localeCompare(b.tool) || a.n - b.n || a.run - b.run)) {
    lines.push(CSV_COLUMNS.map((c) => (Number.isNaN(r[c] as number) ? "" : String(r[c]))).join(","));
  }
  return lines.join("\n") + "\n";
}

/** CSV consolidado (média ± IC95% por ferramenta e volume). */
export function toSummaryCsv(rows: Row[]): string {
  const metrics: Metric[] = ["rtt_ms", "mem_obs_mb", "cpu_obs", "cpu_waf", "mem_waf_mb", "inspect_avg_ms", "inspect_pct"];
  const byMetric = Object.fromEntries(metrics.map((m) => [m, summary(rows, m)])) as Record<Metric, ReturnType<typeof summary>>;
  const base = byMetric.rtt_ms;
  const header = [
    "ferramenta", "n", "repeticoes",
    "rtt_mean_ms", "rtt_ci95_ms",
    "mem_obs_mean_mb", "mem_obs_ci95_mb",
    "cpu_obs_mean_pct", "cpu_obs_ci95_pct",
    "cpu_waf_mean_pct", "cpu_waf_ci95_pct",
    "mem_waf_mean_mb", "mem_waf_ci95_mb",
    "inspect_avg_mean_ms", "inspect_pct_mean",
  ];
  const lines = [header.join(",")];
  for (const item of base) {
    const find = (m: Metric) => byMetric[m].find((x) => x.Ferramenta === item.Ferramenta && x.n === item.n);
    const memObs = find("mem_obs_mb");
    const cpuObs = find("cpu_obs");
    const cpuWaf = find("cpu_waf");
    const memWaf = find("mem_waf_mb");
    const inspAvg = find("inspect_avg_ms");
    const inspPct = find("inspect_pct");
    const fmt = (v?: number, d = 4) => (v !== undefined && Number.isFinite(v) ? v.toFixed(d) : "");
    lines.push([
      item.Ferramenta,
      item.n,
      item.count,
      fmt(item.mean, 4), fmt(item.ci, 4),
      fmt(memObs?.mean, 3), fmt(memObs?.ci, 3),
      fmt(cpuObs?.mean, 3), fmt(cpuObs?.ci, 3),
      fmt(cpuWaf?.mean, 3), fmt(cpuWaf?.ci, 3),
      fmt(memWaf?.mean, 3), fmt(memWaf?.ci, 3),
      fmt(inspAvg?.mean, 4), fmt(inspPct?.mean, 2),
    ].join(","));
  }
  return lines.join("\n") + "\n";
}
