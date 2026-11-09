import type { ReactNode } from "react";
import { COLOR, Tool } from "../lib/analytics";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`min-w-0 rounded-xl border border-line bg-surface p-4 sm:p-5 ${className}`}>{children}</section>;
}

export function SectionTitle({ title, sub, tag }: { title: string; sub?: string; tag?: string }) {
  return (
    <div className="mb-3">
      <div className="flex items-start justify-between gap-2 sm:items-center sm:gap-3">
        <h2 className="text-[15px] font-bold leading-snug tracking-tight">{title}</h2>
        {tag && <span className="shrink-0 whitespace-nowrap rounded-md border border-line px-2 py-0.5 text-xs text-muted">{tag}</span>}
      </div>
      {sub && <p className="mt-1 text-[13px] leading-relaxed text-muted">{sub}</p>}
    </div>
  );
}

export function Dot({ tool }: { tool: Tool }) {
  return <i className="inline-block h-[7px] w-[7px] shrink-0 rounded-full" style={{ background: COLOR[tool] }} />;
}

export function Info({ children }: { children: ReactNode }) {
  return (
    <p role="note" className="rounded-lg border border-tagline bg-tag px-4 py-3 text-[13px] leading-relaxed text-tagink">
      {children}
    </p>
  );
}

export function Toggle({ checked, onChange, label, disabled = false }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <label className={`flex items-center gap-2.5 text-sm ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? "bg-accent" : "bg-track"}`}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${checked ? "left-[18px]" : "left-0.5"}`} />
      </button>
      <span className="text-[13px] sm:text-sm">{label}</span>
    </label>
  );
}

export function Select<T extends string | number>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-semibold">
      {label}
      <select
        value={value}
        onChange={(e) => onChange((typeof value === "number" ? Number(e.target.value) : e.target.value) as T)}
        className="w-full max-w-sm rounded-lg border border-line bg-surface px-3 py-2 text-sm font-normal"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}
