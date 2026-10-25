import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
  testid,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  testid?: string;
}) {
  return (
    <section
      data-testid={testid}
      className={cn("rounded-xl border border-border bg-card transition-colors duration-200 panel-grid-glow", className)}
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3.5">
        <div>
          <h2 className="font-heading text-sm font-semibold tracking-tight">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p> : null}
        </div>
        {actions}
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Kpi({
  label,
  value,
  sub,
  testid,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  testid?: string;
  accent?: "cyan" | "orange" | "emerald" | "amber" | "rose";
}) {
  const accentClass =
    accent === "cyan"
      ? "text-sky-400"
      : accent === "emerald"
        ? "text-emerald-400"
        : accent === "amber"
          ? "text-amber-400"
          : accent === "rose"
            ? "text-rose-400"
            : "text-orange-400";
  return (
    <div
      data-testid={testid}
      className="rounded-xl border border-border bg-[#151d2c] p-4 transition-colors duration-200 panel-grid-glow dark:bg-[#151d2c]"
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className={cn("mt-2 font-mono text-2xl font-medium tracking-tight", accentClass)}>{value}</p>
      {sub ? <p className="mt-1 text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

export function Figure({ label, value, sub, testid }: { label: string; value: string; sub?: string; testid?: string }) {
  return (
    <div data-testid={testid} className="rounded-lg border border-border bg-muted/40 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-lg">{value}</p>
      {sub ? <p className="mt-0.5 text-[11px] text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

const ROUTE_STYLES: Record<string, string> = {
  security_team: "bg-[#450a0a] text-[#fca5a5] border border-[#7f1d1d]/60",
  premium_desk: "bg-[#3b1d04] text-[#fdbA74] border border-[#9a3412]/50",
  support_queue: "bg-[#0c2a4d] text-[#7dd3fc] border border-[#075985]/60",
  human_review: "bg-[#2e1065] text-[#d8b4fe] border border-[#6d28d9]/50",
};

export function RouteBadge({ route, testid }: { route: string; testid?: string }) {
  return (
    <span
      data-testid={testid}
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${ROUTE_STYLES[route] ?? "bg-muted text-muted-foreground border border-border"}`}
    >
      {route.replace(/_/g, " ")}
    </span>
  );
}

export function PriorityBadge({ priority, testid }: { priority: string; testid?: string }) {
  return (
    <span
      data-testid={testid}
      className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[11px] ${
        priority === "HIGH" ? "bg-amber-400/10 text-amber-400 border border-amber-400/30" : "text-muted-foreground border border-border"
      }`}
    >
      {priority}
    </span>
  );
}

export function MonoNote({ children, testid }: { children: ReactNode; testid?: string }) {
  return (
    <pre
      data-testid={testid}
      className="overflow-x-auto rounded-lg border border-border bg-[#070a0f] p-3 font-mono text-[11px] leading-relaxed text-sky-300"
    >
      {children}
    </pre>
  );
}