import { describe, expect, it } from "vitest";
import { confidenceSeparated, meanByTool, number, Row, summary, Tool, volume } from "./analytics";
import { ALL_VOLUMES, DATA, DATA_OTIMIZADA, toCsv, toSummaryCsv } from "./data";

const fake = (tool: Tool, values: number[]): Row[] =>
  values.map((v, i) => ({ Ferramenta: tool, tool: tool.toLowerCase(), n: 100000, N: "100 mil", run: i + 1, rtt_ms: v } as Row));

describe("resultados originais e intervalos", () => {
  it("reproduz a média e o IC95% do eBPF em 100 mil", () => {
    const first = summary(DATA, "rtt_ms").find((g) => g.Ferramenta === "eBPF" && g.n === 100000)!;
    expect(first.mean).toBeCloseTo(0.5331, 4);
    expect(first.ci).toBeCloseTo(0.0029, 4);
    expect(first.count).toBe(30);
  });

  it("separa os ICs de eBPF e Sysstat nos quatro volumes", () => {
    expect(confidenceSeparated(DATA, "eBPF", "Sysstat")).toBe(true);
  });

  it("não afirma separação quando os ICs se sobrepõem ou há uma só repetição", () => {
    const rows = [...fake("eBPF", [0.1, 1, 1.9]), ...fake("Sysstat", [0.2, 1.1, 2])];
    expect(confidenceSeparated(rows, "eBPF", "Sysstat")).toBe(false);
    expect(confidenceSeparated([rows[0], rows[3]], "eBPF", "Sysstat")).toBe(false);
  });

  it("não afirma separação global se faltar uma ferramenta em um volume", () => {
    const rows = DATA.filter((r) => !(r.Ferramenta === "Sysstat" && r.n === 100000));
    expect(confidenceSeparated(rows, "eBPF", "Sysstat")).toBe(false);
  });
});

describe("dados e formatação", () => {
  it("carrega as 480 execuções oficiais e as 480 otimizadas nos quatro volumes", () => {
    expect(DATA).toHaveLength(480);
    expect(DATA_OTIMIZADA).toHaveLength(480);
    expect(ALL_VOLUMES).toEqual([100000, 500000, 1000000, 2000000]);
  });

  it("mantém a ordem eBPF < Sysstat < Prometheus < Docker no RTT em ambas as baterias", () => {
    expect(meanByTool(DATA, "rtt_ms").map(([t]) => t)).toEqual(["eBPF", "Sysstat", "Prometheus", "Docker"]);
    expect(meanByTool(DATA_OTIMIZADA, "rtt_ms").map(([t]) => t)).toEqual(["eBPF", "Sysstat", "Prometheus", "Docker"]);
  });

  it("calcula inspect_pct = 100% em todas as execuções da bateria otimizada", () => {
    expect(DATA_OTIMIZADA.every((r) => r.inspect_pct === 100)).toBe(true);
  });

  it("formata números e volumes em pt-BR", () => {
    expect(number(1234.5, 1)).toBe("1.234,5");
    expect(volume(100000)).toBe("100 mil");
    expect(volume(1000000)).toBe("1 M");
    expect(volume(2000000)).toBe("2 M");
  });

  it("exporta o CSV do recorte com as colunas originais", () => {
    const csv = toCsv(DATA.filter((r) => r.Ferramenta === "Docker" && r.n === 100000));
    const lines = csv.trim().split("\n");
    expect(lines).toHaveLength(31);
    expect(lines[0]).toBe("tool,n,run,rtt_ms,rtt_std_ms,cpu_waf,mem_waf_mb,cpu_obs,mem_obs_mb,inspect_count,inspect_avg_ms,bytes_rx,bytes_tx");
    expect(lines.slice(1).every((l) => l.startsWith("docker,100000,"))).toBe(true);
  });

  it("exporta o CSV de resumo agregado (Média ± IC95%) com 16 combinações", () => {
    const csv = toSummaryCsv(DATA);
    const lines = csv.trim().split("\n");
    expect(lines).toHaveLength(17);
    expect(lines[0]).toContain("rtt_mean_ms,rtt_ci95_ms");
  });
});
