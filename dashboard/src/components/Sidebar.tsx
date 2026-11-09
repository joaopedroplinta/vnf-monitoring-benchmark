import { COLOR, TOOLS, Tool, volume } from "../lib/analytics";
import { ALL_VOLUMES, DATASETS, DatasetId } from "../lib/data";
import { ChevronLeft, ChevronRight, ClipboardList, Database, Gauge, House, LineChart, ListFilter, Monitor, Moon, Sun, Timer, X } from "lucide-react";
import type { ThemeMode } from "../lib/theme";
import { Toggle } from "./ui";

export interface Filters {
  dataset: DatasetId;
  tools: Tool[];
  volumes: number[];
  log: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  dataset: "oficial",
  tools: [...TOOLS],
  volumes: [...ALL_VOLUMES],
  log: false,
};

function Chip({ on, onClick, children, color }: { on: boolean; onClick: () => void; children: string; color?: string }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[13px] transition-colors ${
        on ? "border-tagline bg-tag text-tagink" : "border-line bg-surface text-muted hover:text-ink"
      }`}
    >
      {color && <i className="h-[7px] w-[7px] rounded-full" style={{ background: color, opacity: on ? 1 : 0.4 }} />}
      {children}
    </button>
  );
}

const toggle = <T,>(list: T[], item: T) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

export const NAV = [
  { name: "Visão geral", icon: House },
  { name: "Latência", icon: Timer },
  { name: "Recursos", icon: Gauge },
  { name: "Execuções", icon: LineChart },
  { name: "Dados", icon: Database },
  { name: "Metodologia", icon: ClipboardList },
] as const;
export type TabName = (typeof NAV)[number]["name"];

const THEMES = [
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
  { value: "system", label: "Sistema", icon: Monitor },
] as const;

function Label({ children }: { children: string }) {
  return <legend className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">{children}</legend>;
}

interface SidebarProps {
  filters: Filters;
  onChange: (f: Filters) => void;
  tab: TabName;
  onTab: (t: TabName) => void;
  mode: ThemeMode;
  onMode: (m: ThemeMode) => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function Sidebar({ filters, onChange, tab, onTab, mode, onMode, mobileOpen, onCloseMobile, collapsed, onToggleCollapsed }: SidebarProps) {
  // Trilho de ícones só existe no desktop; na gaveta do celular o conteúdo é sempre completo.
  const wide = "lg:hidden"; // esconde no trilho
  const hide = collapsed ? wide : "";
  const activeFilters = (filters.tools.length < TOOLS.length ? 1 : 0) + (filters.volumes.length < ALL_VOLUMES.length ? 1 : 0) + (filters.dataset !== "oficial" ? 1 : 0) + (filters.log ? 1 : 0);

  return (
    <>
      {mobileOpen && <div aria-hidden="true" onClick={onCloseMobile} className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[1px] lg:hidden" />}

      <aside
        aria-label="Navegação e filtros"
        className={`fixed inset-y-0 left-0 z-50 flex w-[290px] max-w-[85vw] flex-col border-r border-line bg-sidebar shadow-2xl transition-[transform,width] duration-200 ease-out lg:sticky lg:top-0 lg:z-20 lg:h-screen lg:shrink-0 lg:translate-x-0 lg:shadow-none ${
          collapsed ? "lg:w-[68px]" : "lg:w-[290px]"
        } ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        {/* Marca */}
        <div className={`flex h-16 shrink-0 items-center justify-between gap-2 border-b border-line px-4 ${collapsed ? "lg:justify-center lg:px-0" : ""}`}>
          <div className="flex min-w-0 items-center gap-2.5">
            <svg viewBox="0 0 40 40" fill="none" aria-hidden="true" className="h-8 w-8 shrink-0 text-accent">
              <path d="M10 10L30 10L20 30Z" stroke="currentColor" strokeWidth="1.5" />
              <path d="M10 10L20 18L30 10M20 18V30" stroke="currentColor" strokeWidth="1.5" />
              {[[10, 10], [30, 10], [20, 30]].map(([x, y]) => (
                <circle key={`${x}${y}`} cx={x} cy={y} r="4" fill="var(--sidebar)" stroke="currentColor" strokeWidth="2" />
              ))}
              <circle cx="20" cy="18" r="2" fill="currentColor" />
            </svg>
            <div className={`min-w-0 ${hide}`}>
              <strong className="block truncate text-base leading-tight tracking-tight">VNF Lab</strong>
              <span className="block truncate text-[11px] text-muted">Benchmark TCC</span>
            </div>
          </div>
          <button type="button" onClick={onCloseMobile} aria-label="Fechar menu" className="rounded-lg p-1.5 text-muted hover:bg-strip hover:text-ink lg:hidden">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="sidebar-scroll flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto overflow-x-hidden px-3 py-4">
          {/* Navegação */}
          <nav aria-label="Seções">
            <ul className="flex flex-col gap-0.5">
              {NAV.map((n) => {
                const active = tab === n.name;
                return (
                  <li key={n.name}>
                    <button
                      type="button"
                      onClick={() => { onTab(n.name); onCloseMobile(); }}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? n.name : undefined}
                      className={`relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${collapsed ? "lg:justify-center lg:px-0" : ""} ${
                        active ? "bg-tag text-tagink" : "text-muted hover:bg-strip hover:text-ink"
                      }`}
                    >
                      {active && <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r bg-accent" />}
                      <n.icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                      <span className={hide}>{n.name}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Filtros */}
          {collapsed ? (
            <button type="button" onClick={onToggleCollapsed} title="Filtros" aria-label="Abrir filtros" className="relative hidden items-center justify-center rounded-lg py-2 text-muted hover:bg-strip hover:text-ink lg:flex">
              <ListFilter className="h-[18px] w-[18px]" />
              {activeFilters > 0 && <span className="absolute right-3 top-1.5 h-2 w-2 rounded-full bg-accent" />}
            </button>
          ) : null}

          <div className={`flex flex-col gap-4 border-t border-line pt-4 ${hide}`}>
            <div className="flex items-center justify-between px-1">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted">Filtros</h2>
              <button type="button" onClick={() => onChange(DEFAULT_FILTERS)} disabled={activeFilters === 0} className="text-xs font-medium text-accent hover:underline disabled:cursor-default disabled:text-muted disabled:no-underline disabled:opacity-60">
                Restaurar
              </button>
            </div>

            <fieldset className="flex flex-col gap-1.5 px-1">
              <Label>Bateria experimental</Label>
              <div role="radiogroup" className="flex flex-col gap-1.5">
                {(Object.keys(DATASETS) as DatasetId[]).map((id) => {
                  const active = filters.dataset === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => onChange({ ...filters, dataset: id })}
                      className={`rounded-lg border px-3 py-1.5 text-left text-[13px] transition-colors ${active ? "border-tagline bg-tag font-semibold text-tagink" : "border-line bg-surface text-muted hover:text-ink"}`}
                    >
                      {DATASETS[id].label}
                    </button>
                  );
                })}
              </div>
              <p className="text-[11.5px] leading-relaxed text-muted">{DATASETS[filters.dataset].desc}</p>
            </fieldset>

            <fieldset className="px-1">
              <Label>Ferramentas</Label>
              <div className="flex flex-wrap gap-1.5">
                {TOOLS.map((t) => (
                  <Chip key={t} on={filters.tools.includes(t)} color={COLOR[t]} onClick={() => onChange({ ...filters, tools: toggle(filters.tools, t) })}>{t}</Chip>
                ))}
              </div>
            </fieldset>

            <fieldset className="px-1">
              <Label>Volume nominal (N)</Label>
              <div className="flex flex-wrap gap-1.5">
                {ALL_VOLUMES.map((n) => (
                  <Chip key={n} on={filters.volumes.includes(n)} onClick={() => onChange({ ...filters, volumes: toggle(filters.volumes, n) })}>{volume(n)}</Chip>
                ))}
              </div>
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
                {filters.dataset === "oficial"
                  ? "Na coleta oficial (1 proc.), N ≥ 500k processa 62% a 88% do arquivo na janela."
                  : "Na bateria de inspeção integral (4 proc.), o WAF processa 100% de N em todos os volumes."}
              </p>
            </fieldset>

            <div className="px-1">
              <Toggle checked={filters.log} onChange={(log) => onChange({ ...filters, log })} label="Escala logarítmica de RTT" />
            </div>
          </div>
        </div>

        {/* Rodapé fixo: tema, recolher, GitHub */}
        <div className="shrink-0 border-t border-line p-3">
          <div className={`flex flex-col gap-2 ${collapsed ? "lg:items-center" : ""}`}>
            <div role="group" aria-label="Tema" className={`flex gap-0.5 rounded-lg border border-line bg-strip p-0.5 text-xs ${hide}`}>
              {THEMES.map((t) => (
                <button key={t.value} type="button" aria-pressed={mode === t.value} onClick={() => onMode(t.value)} className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 transition-colors ${mode === t.value ? "bg-surface font-semibold text-ink shadow-sm" : "text-muted hover:text-ink"}`}>
                  <t.icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {t.label}
                </button>
              ))}
            </div>
            {collapsed && (() => {
              const i = THEMES.findIndex((t) => t.value === mode);
              const next = THEMES[(i + 1) % THEMES.length];
              const Cur = THEMES[i].icon;
              return (
                <button type="button" onClick={() => onMode(next.value)} title={`Tema: ${THEMES[i].label} (trocar para ${next.label})`} aria-label={`Tema: ${THEMES[i].label}. Trocar para ${next.label}`} className="hidden items-center justify-center rounded-lg py-2 text-muted hover:bg-strip hover:text-ink lg:flex">
                  <Cur className="h-[18px] w-[18px]" />
                </button>
              );
            })()}
            <div className={`flex items-center justify-between gap-2 px-1 text-[11.5px] text-muted ${hide}`}>
              <span className="truncate">IFPR Pinhais · 2026</span>
              <a className="font-medium text-accent hover:underline" href="https://github.com/joaopedroplinta/vnf-monitoring-benchmark" target="_blank" rel="noopener noreferrer">GitHub</a>
            </div>
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Expandir barra lateral" : "Recolher barra lateral"}
              title={collapsed ? "Expandir" : "Recolher"}
              className={`hidden items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted hover:bg-strip hover:text-ink lg:flex ${collapsed ? "justify-center px-0" : ""}`}
            >
              {collapsed ? <ChevronRight className="h-[18px] w-[18px]" /> : <ChevronLeft className="h-[18px] w-[18px]" />}
              <span className={hide}>Recolher</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
