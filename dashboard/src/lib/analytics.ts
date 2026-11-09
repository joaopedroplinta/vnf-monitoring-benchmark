/** Agregações do benchmark, compartilhadas pelas visualizações. */

export const LABEL = {
  ebpf: "eBPF",
  sysstat: "Sysstat",
  prometheus: "Prometheus",
  docker: "Docker",
} as const;

export type Tool = (typeof LABEL)[keyof typeof LABEL];
export const TOOLS: Tool[] = ["eBPF", "Sysstat", "Prometheus", "Docker"];

/** Tons com contraste nas superfícies dos dois temas. */
export const COLOR: Record<Tool, string> = {
  eBPF: "#2196F3",
  Sysstat: "#FF9800",
  Prometheus: "#4CAF50",
  Docker: "#9C27B0",
};

export interface Row {
  tool: string;
  Ferramenta: Tool;
  n: number;
  N: string;
  run: number;
  rtt_ms: number;
  rtt_std_ms: number;
  cpu_waf: number;
  mem_waf_mb: number;
  cpu_obs: number;
  mem_obs_mb: number;
  inspect_count: number;
  inspect_avg_ms: number;
  inspect_pct: number;
  bytes_rx: number;
  bytes_tx: number;
}

export type Metric =
  | "rtt_ms"
  | "cpu_waf"
  | "mem_waf_mb"
  | "cpu_obs"
  | "mem_obs_mb"
  | "inspect_avg_ms"
  | "inspect_pct";

export const METRICS: Record<Exclude<Metric, "rtt_ms">, string> = {
  mem_obs_mb: "Memória do observador (MB)",
  cpu_obs: "CPU do observador (%)",
  cpu_waf: "CPU do WAF (%)",
  mem_waf_mb: "Memória do WAF (MB)",
  inspect_avg_ms: "Validação · Tempo médio de inspeção do WAF (ms)",
  inspect_pct: "Validação · Mensagens inspecionadas (% de N)",
};

export const RUN_METRICS: Record<Metric, string> = {
  rtt_ms: "Tempo de resposta do observador (RTT, ms)",
  mem_obs_mb: "Memória do observador (MB)",
  cpu_obs: "CPU do observador (%)",
  cpu_waf: "CPU do WAF (%)",
  mem_waf_mb: "Memória do WAF (MB)",
  inspect_avg_ms: "Tempo médio de inspeção do WAF (ms)",
  inspect_pct: "Mensagens inspecionadas (% de N)",
};

/** t de Student bicaudal (95%) para 1 a 29 graus de liberdade. */
const T95: Record<number, number> = {
  1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
  9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.16, 14: 2.145, 15: 2.131, 16: 2.12,
  17: 2.11, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.08, 22: 2.074, 23: 2.069, 24: 2.064,
  25: 2.06, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
};

export function number(value: number, decimals = 0): string {
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function volume(value: number): string {
  if (value >= 1_000_000) return `${number(value / 1_000_000, 1).replace(/,0$/, "")} M`;
  if (value >= 1_000) return `${number(value / 1_000, 1).replace(/,0$/, "")} mil`;
  return number(value);
}

const finite = (v: number) => Number.isFinite(v);

export function mean(values: number[]): number {
  const ok = values.filter(finite);
  return ok.length ? ok.reduce((a, b) => a + b, 0) / ok.length : NaN;
}

/** Desvio-padrão amostral (ddof = 1), como o pandas. */
function std(values: number[]): number {
  if (values.length < 2) return NaN;
  const m = mean(values);
  return Math.sqrt(values.reduce((a, v) => a + (v - m) ** 2, 0) / (values.length - 1));
}

export interface Summary {
  Ferramenta: Tool;
  n: number;
  N: string;
  mean: number;
  std: number;
  count: number;
  ci: number;
}

/** Média, desvio e IC95% por ferramenta e volume, ordenado por volume. */
export function summary(rows: Row[], metric: Metric): Summary[] {
  const groups = new Map<string, { first: Row; values: number[] }>();
  for (const r of rows) {
    const key = `${r.Ferramenta}|${r.n}`;
    const g = groups.get(key) ?? { first: r, values: [] };
    if (finite(r[metric])) g.values.push(r[metric]);
    groups.set(key, g);
  }
  const out: Summary[] = [];
  for (const { first, values } of groups.values()) {
    const count = values.length;
    const s = std(values);
    const ci = count > 1 ? ((T95[count - 1] ?? 1.96) * s) / Math.sqrt(count) : NaN;
    out.push({ Ferramenta: first.Ferramenta, n: first.n, N: first.N, mean: mean(values), std: s, count, ci });
  }
  return out.sort((a, b) => a.n - b.n || TOOLS.indexOf(a.Ferramenta) - TOOLS.indexOf(b.Ferramenta));
}

/** Verifica a separação dos ICs por volume, sem misturar cargas distintas. */
export function confidenceSeparated(rows: Row[], first: Tool, second: Tool): boolean {
  if (rows.length === 0) return false;
  const s = summary(rows, "rtt_ms");
  for (const n of new Set(rows.map((r) => r.n))) {
    const a = s.find((g) => g.n === n && g.Ferramenta === first);
    const b = s.find((g) => g.n === n && g.Ferramenta === second);
    if (!a || !b || Number.isNaN(a.ci) || Number.isNaN(b.ci)) return false;
    if (a.mean + a.ci >= b.mean - b.ci) return false;
  }
  return true;
}

/** Média de uma métrica por ferramenta, da menor para a maior. */
export function meanByTool(rows: Row[], metric: Metric): [Tool, number][] {
  const out: [Tool, number][] = [];
  for (const tool of TOOLS) {
    const m = mean(rows.filter((r) => r.Ferramenta === tool).map((r) => r[metric]));
    if (finite(m)) out.push([tool, m]);
  }
  return out.sort((a, b) => a[1] - b[1]);
}
