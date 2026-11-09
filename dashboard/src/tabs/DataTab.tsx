import { useState } from "react";
import { number, summary, Tool, volume } from "../lib/analytics";
import { toCsv, toSummaryCsv } from "../lib/data";
import { Dot, SectionTitle } from "../components/ui";
import type { TabProps } from "./types";

const RAW_COLUMNS: {
  key: "tool" | "n" | "run" | "rtt_ms" | "rtt_std_ms" | "mem_obs_mb" | "cpu_obs" | "mem_waf_mb" | "cpu_waf" | "inspect_count" | "inspect_pct" | "inspect_avg_ms" | "bytes_rx" | "bytes_tx";
  label: string;
  decimals?: number;
}[] = [
  { key: "tool", label: "Ferramenta" },
  { key: "n", label: "N nominal" },
  { key: "run", label: "Exec." },
  { key: "rtt_ms", label: "RTT (ms)", decimals: 4 },
  { key: "rtt_std_ms", label: "DP RTT (ms)", decimals: 4 },
  { key: "mem_obs_mb", label: "Mem. Obs (MB)", decimals: 2 },
  { key: "cpu_obs", label: "CPU Obs (%)", decimals: 3 },
  { key: "mem_waf_mb", label: "Mem. WAF (MB)", decimals: 2 },
  { key: "cpu_waf", label: "CPU WAF (%)", decimals: 2 },
  { key: "inspect_count", label: "Inspecionadas", decimals: 0 },
  { key: "inspect_pct", label: "% de N", decimals: 1 },
  { key: "inspect_avg_ms", label: "T. Insp. (ms)", decimals: 4 },
  { key: "bytes_rx", label: "Bytes RX", decimals: 0 },
  { key: "bytes_tx", label: "Bytes TX", decimals: 0 },
];

function download(text: string, filename: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function DataTab({ view, tools, dataset }: TabProps) {
  const [mode, setMode] = useState<"summary" | "raw">("summary");
  const rows = [...view].sort((a, b) => a.tool.localeCompare(b.tool) || a.n - b.n || a.run - b.run);

  const rttSum = summary(view, "rtt_ms");
  const memObsSum = summary(view, "mem_obs_mb");
  const cpuObsSum = summary(view, "cpu_obs");
  const cpuWafSum = summary(view, "cpu_waf");
  const memWafSum = summary(view, "mem_waf_mb");
  const inspMsSum = summary(view, "inspect_avg_ms");
  const inspPctSum = summary(view, "inspect_pct");

  const findStat = (list: ReturnType<typeof summary>, t: Tool, n: number) =>
    list.find((g) => g.Ferramenta === t && g.n === n);

  const volumes = [...new Set(view.map((r) => r.n))].sort((a, b) => a - b);
  const summaryPairs = tools.flatMap((t) => volumes.map((n) => ({ tool: t, n })));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionTitle
          title="Resultados disponíveis para conferência"
          sub="Alterne entre a tabela consolidada (Média ± IC95%, igual às tabelas do Capítulo 4) e as 480 execuções individuais."
        />
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-line bg-surface p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setMode("summary")}
              className={`rounded-md px-3 py-1.5 font-medium transition ${
                mode === "summary" ? "bg-accent/15 text-accent font-semibold" : "text-muted hover:text-ink"
              }`}
            >
              Resumo (Média ± IC95%)
            </button>
            <button
              type="button"
              onClick={() => setMode("raw")}
              className={`rounded-md px-3 py-1.5 font-medium transition ${
                mode === "raw" ? "bg-accent/15 text-accent font-semibold" : "text-muted hover:text-ink"
              }`}
            >
              Execuções individuais ({rows.length})
            </button>
          </div>
          <button
            type="button"
            onClick={() =>
              mode === "summary"
                ? download(toSummaryCsv(view), `resumo_ic95_${dataset}.csv`)
                : download(toCsv(view), `execucoes_${dataset}.csv`)
            }
            className="rounded-lg border border-line bg-surface px-3.5 py-1.5 text-xs font-semibold hover:border-accent"
          >
            {mode === "summary" ? "Baixar resumo CSV (IC95%)" : "Baixar execuções CSV"}
          </button>
        </div>
      </div>

      {mode === "summary" ? (
        <div className="max-h-[460px] overflow-auto rounded-xl border border-line bg-surface">
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="sticky top-0 bg-strip text-left">
              <tr>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">Ferramenta</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">Volume (N)</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">Exec.</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">RTT ± IC95% (ms)</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">Mem. Obs ± IC95% (MB)</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">CPU Obs ± IC95% (%)</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">CPU WAF ± IC95% (%)</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">Mem. WAF ± IC95% (MB)</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">T. Insp. (ms)</th>
                <th className="whitespace-nowrap px-3 py-2.5 font-semibold">% de N insp.</th>
              </tr>
            </thead>
            <tbody>
              {summaryPairs.map(({ tool, n }) => {
                const rtt = findStat(rttSum, tool, n);
                const memO = findStat(memObsSum, tool, n);
                const cpuO = findStat(cpuObsSum, tool, n);
                const cpuW = findStat(cpuWafSum, tool, n);
                const memW = findStat(memWafSum, tool, n);
                const inspMs = findStat(inspMsSum, tool, n);
                const inspPct = findStat(inspPctSum, tool, n);
                if (!rtt) return null;
                return (
                  <tr key={`${tool}-${n}`} className="border-t border-line">
                    <td className="whitespace-nowrap px-3 py-2 font-medium">
                      <span className="inline-flex items-center gap-1.5"><Dot tool={tool} />{tool}</span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">{volume(n)}</td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums text-muted">{rtt.count}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-semibold tabular-nums">
                      {number(rtt.mean, 4)} <span className="font-normal text-muted">± {number(rtt.ci, 4)}</span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {memO ? <>{number(memO.mean, 2)} <span className="text-muted">± {number(memO.ci, 2)}</span></> : "—"}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {cpuO ? <>{number(cpuO.mean, 3)} <span className="text-muted">± {number(cpuO.ci, 3)}</span></> : "—"}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {cpuW ? <>{number(cpuW.mean, 2)} <span className="text-muted">± {number(cpuW.ci, 2)}</span></> : "—"}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {memW ? <>{number(memW.mean, 2)} <span className="text-muted">± {number(memW.ci, 2)}</span></> : "—"}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {inspMs ? number(inspMs.mean, 4) : "—"}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                      {inspPct ? `${number(inspPct.mean, 1)}%` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="max-h-[460px] overflow-auto rounded-xl border border-line bg-surface">
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="sticky top-0 bg-strip text-left">
              <tr>{RAW_COLUMNS.map((c) => <th key={c.key} className="whitespace-nowrap px-3 py-2.5 font-semibold">{c.label}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.tool}-${r.n}-${r.run}`} className="border-t border-line">
                  {RAW_COLUMNS.map((c) => (
                    <td key={c.key} className="whitespace-nowrap px-3 py-1.5 tabular-nums">
                      {c.key === "tool" ? r.Ferramenta : Number.isNaN(r[c.key]) ? "" : number(r[c.key] as number, c.decimals ?? 0)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <details className="rounded-xl border border-line bg-surface px-4 py-3 text-[13px] leading-relaxed text-muted">
        <summary className="cursor-pointer font-semibold text-ink">Como interpretar as colunas e métricas de validação</summary>
        <p className="mt-2">
          <b className="text-ink">RTT:</b> tempo de resposta do observador ao probe UDP.{" "}
          <b className="text-ink">N nominal:</b> total de mensagens enviadas pelo gerador de carga.{" "}
          <b className="text-ink">Inspecionadas (% de N):</b> mensagens efetivamente processadas pelo WAF dentro da janela da execução (62% a 100% na coleta oficial de 1 processo; 100% na bateria otimizada de 4 processos).{" "}
          <b className="text-ink">T. Insp. (ms):</b> tempo médio por inspeção de regex no WAF (~0,080 ms na coleta oficial), usado como validação funcional de que o motor operou de forma idêntica sob os quatro observadores.{" "}
          <b className="text-ink">Bytes RX/TX:</b> tráfego contabilizado pelo observador — o agente <b className="text-ink">eBPF</b> filtra no kernel apenas os sockets TCP da porta <code className="rounded bg-strip px-1 py-0.5">8080</code> do WAF (~123 MB em 2 M), enquanto Sysstat, Prometheus e Docker leem os contadores agregados da interface <code className="rounded bg-strip px-1 py-0.5">lo</code> (~212 MB, somando ida e volta em loopback).
        </p>
      </details>
    </div>
  );
}
