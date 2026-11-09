import { useEffect, useMemo, useState } from "react";
import { TOOLS, Tool, number } from "./lib/analytics";
import { ALL_VOLUMES, DATASETS, DatasetId } from "./lib/data";
import { useTheme } from "./lib/theme";
import { DEFAULT_FILTERS, Filters, NAV, Sidebar, TabName } from "./components/Sidebar";
import { Overview } from "./tabs/Overview";
import { Latency } from "./tabs/Latency";
import { Resources } from "./tabs/Resources";
import { Runs } from "./tabs/Runs";
import { DataTab } from "./tabs/DataTab";
import { Method } from "./tabs/Method";

const TABS = NAV.map((n) => n.name) as readonly TabName[];

function readUrlState(): { filters: Filters; tab: TabName } {
  if (typeof window === "undefined") return { filters: DEFAULT_FILTERS, tab: "Visão geral" };
  const params = new URLSearchParams(window.location.search);
  const tabParam = params.get("tab") as TabName | null;
  const tab = tabParam && TABS.includes(tabParam) ? tabParam : "Visão geral";
  const dsParam = params.get("ds") as DatasetId | null;
  const dataset: DatasetId = dsParam === "otimizada" ? "otimizada" : "oficial";
  const toolsParam = params.get("tools");
  const tools = toolsParam
    ? TOOLS.filter((t) => toolsParam.split(",").includes(t))
    : DEFAULT_FILTERS.tools;
  const volParam = params.get("vol");
  const volumes = volParam
    ? ALL_VOLUMES.filter((v) => volParam.split(",").map(Number).includes(v))
    : DEFAULT_FILTERS.volumes;
  const log = params.get("log") === "1";

  return {
    tab,
    filters: {
      dataset,
      tools: tools.length ? (tools as Tool[]) : DEFAULT_FILTERS.tools,
      volumes: volumes.length ? volumes : DEFAULT_FILTERS.volumes,
      log,
    },
  };
}

function Stat({ value, label, className = "" }: { value: React.ReactNode; label: string; className?: string }) {
  return (
    <div className={`px-4 py-3.5 sm:px-5 sm:py-4 ${className}`}>
      <strong className="block text-xl font-extrabold tracking-tight sm:text-2xl">{value}</strong>
      <span className="text-xs text-muted">{label}</span>
    </div>
  );
}

export default function App() {
  const initial = useMemo(() => readUrlState(), []);
  const { mode, setMode, dark } = useTheme();
  const [filters, setFilters] = useState<Filters>(initial.filters);
  const [tab, setTab] = useState<TabName>(initial.tab);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams();
    if (tab !== "Visão geral") params.set("tab", tab);
    if (filters.dataset !== "oficial") params.set("ds", filters.dataset);
    if (filters.tools.length !== TOOLS.length) params.set("tools", filters.tools.join(","));
    if (filters.volumes.length !== ALL_VOLUMES.length) params.set("vol", filters.volumes.join(","));
    if (filters.log) params.set("log", "1");
    const qs = params.toString();
    const nextUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    window.history.replaceState(null, "", nextUrl);
  }, [tab, filters]);

  const activeRows = DATASETS[filters.dataset].rows;
  const tools = useMemo(() => TOOLS.filter((t) => filters.tools.includes(t)), [filters.tools]);
  const view = useMemo(
    () => activeRows.filter((r) => filters.tools.includes(r.Ferramenta) && filters.volumes.includes(r.n)),
    [activeRows, filters],
  );

  const counts = new Map<string, number>();
  for (const r of view) counts.set(`${r.Ferramenta}|${r.n}`, (counts.get(`${r.Ferramenta}|${r.n}`) ?? 0) + 1);
  const perCell = [...counts.values()];
  const reps = perCell.length === 0 ? "0" : Math.min(...perCell) === Math.max(...perCell) ? String(perCell[0]) : `${Math.min(...perCell)}–${Math.max(...perCell)}`;
  const avgInspectPct = view.length ? view.reduce((acc, r) => acc + (Number.isFinite(r.inspect_pct) ? r.inspect_pct : 0), 0) / view.length : 0;
  const props = { view, tools, log: filters.log, dark, dataset: filters.dataset };

  return (
    <div className="min-h-screen lg:flex">
      <Sidebar
        filters={filters}
        onChange={setFilters}
        tab={tab}
        onTab={setTab}
        mode={mode}
        onMode={setMode}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((v) => !v)}
      />

      <main className="mx-auto w-full max-w-[1480px] min-w-0 flex-1 px-4 py-5 sm:px-5 sm:py-6 lg:px-10 lg:py-8">
        <div className="mb-5 flex items-center justify-between gap-2 text-[12px] text-muted sm:mb-6 sm:text-[13px]">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Abrir menu"
              className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-ink hover:border-accent lg:hidden"
            >
              <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 text-accent" stroke="currentColor" strokeWidth="1.8">
                <path d="M3 5h14M3 10h14M3 15h10" strokeLinecap="round" />
              </svg>
              Menu
            </button>
            <span className="hidden sm:inline">Pesquisa experimental · Monitoramento de Funções Virtualizadas de Rede</span>
          </div>
          <span className="shrink-0 rounded-md border border-line px-2.5 py-1 text-[11px] font-medium text-ink sm:px-3 sm:py-1.5 sm:text-xs">
            {DATASETS[filters.dataset].shortLabel}
          </span>
        </div>

        <header className="mb-5 sm:mb-6">
          <h1 className="mb-2.5 text-[clamp(24px,3vw,40px)] font-extrabold leading-tight tracking-[-1.2px] sm:mb-3 sm:tracking-[-1.6px]">Quanto custa monitorar uma VNF?</h1>
          <p className="max-w-3xl text-sm leading-relaxed text-muted">
            Quatro abordagens (eBPF, Sysstat, Prometheus e API do Docker) aplicadas ao mesmo WAF. Explore o tempo de resposta do observador, o consumo de recursos e as métricas de validação em 960 execuções.
          </p>
        </header>

        {view.length === 0 ? (
          <div role="status" className="rounded-xl border border-line bg-surface p-6">
            <p className="text-sm">Nenhum resultado neste recorte. Selecione pelo menos uma ferramenta e um volume na lateral, ou restaure os filtros.</p>
            <button type="button" onClick={() => setFilters(DEFAULT_FILTERS)} className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-canvas">
              Mostrar todos os resultados
            </button>
          </div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-2 overflow-hidden rounded-xl border border-line bg-strip md:grid-cols-5">
              <Stat value={number(view.length)} label="execuções no recorte" className="border-b border-r border-line md:border-b-0" />
              <Stat value={<>{tools.length} <small className="text-sm font-normal text-muted">×</small> {new Set(view.map((r) => r.n)).size}</>} label="ferramentas × volumes" className="border-b border-line md:border-b-0 md:border-r" />
              <Stat value={reps} label="repetições por combinação" className="border-b border-r border-line md:border-b-0" />
              <Stat value={<>{number(avgInspectPct, 0)}<small className="text-sm font-normal text-muted">%</small></>} label="média de N inspecionado" className="border-b border-line md:border-b-0 md:border-r" />
              <Stat value={<>95<small className="text-sm font-normal text-muted">%</small></>} label="nível de confiança (t de Student)" className="col-span-2 md:col-span-1" />
            </div>

            <div role="tabpanel">
              {tab === "Visão geral" && <Overview {...props} />}
              {tab === "Latência" && <Latency {...props} />}
              {tab === "Recursos" && <Resources {...props} />}
              {tab === "Execuções" && <Runs {...props} />}
              {tab === "Dados" && <DataTab {...props} />}
              {tab === "Metodologia" && <Method />}
            </div>
          </>
        )}

        <footer className="mt-10 flex flex-wrap justify-between gap-2 border-t border-line pt-4 text-xs text-muted">
          <span>VNF Lab · TCC Ciência da Computação · IFPR Campus Pinhais (2026)</span>
          <span>{number(view.length)} de {number(activeRows.length)} execuções nesta bateria (960 execuções totais)</span>
        </footer>
      </main>
    </div>
  );
}
