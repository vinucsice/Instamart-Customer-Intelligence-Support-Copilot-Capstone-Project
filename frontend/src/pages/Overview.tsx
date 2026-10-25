import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, CircleCheck, CircleAlert } from "lucide-react";
import { apiGet } from "@/lib/api";
import type { OverviewResponse } from "@/lib/types";
import { Kpi } from "@/components/cx/Panel";
import { inr, num } from "@/lib/format";

export default function Overview() {
  const { data, isError } = useQuery({
    queryKey: ["overview"],
    queryFn: () => apiGet<OverviewResponse>("/overview"),
    retry: 1,
  });

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-border bg-card p-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-400">
          Customer Intelligence &amp; Support Copilot
        </p>
        <h1 className="mt-2 font-heading text-3xl font-semibold tracking-tight">
          One trusted tool for the weekly leadership review
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          The raw order exports, retention questions and the support desk's free-text tickets all meet here:
          Part A rebuilds a trusted database, Part B segments customers and predicts lapse, Part C triages
          tickets behind privacy guardrails, Part D answers policy questions and runs the refund agent.
          Every number below is produced by the committed pipeline — nothing is mocked.
        </p>
      </section>

      {isError ? (
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive" data-testid="overview-unavailable-note">
          Pipeline outputs are not reachable right now (backend offline or pipeline not run). The rest of the
          page still renders; run the README's Reproduce commands to populate them.
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4" data-testid="overview-kpi-strip">
        <Kpi label="Customers" value={data ? num(data.totals.customers) : "—"} sub="clean customer table" testid="kpi-customers" accent="cyan" />
        <Kpi label="Raw order rows" value={data ? num(data.totals.raw_order_rows) : "—"} sub={`${num(data?.totals.clean_order_rows ?? 0)} after cleaning`} testid="kpi-raw-orders" accent="orange" />
        <Kpi label="Completed revenue" value={data ? inr(data.totals.completed_revenue_inr) : "—"} sub={`${num(data?.totals.completed_orders ?? 0)} completed orders`} testid="kpi-revenue" accent="emerald" />
        <Kpi label="Support tickets" value={data ? num(data.totals.tickets) : "—"} sub={`${num(data?.totals.segmented_customers ?? 0)} customers segmented`} testid="kpi-tickets" accent="amber" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {(data?.parts ?? []).map((p) => (
          <Link
            key={p.part}
            to={p.part === "A" ? "/data-quality" : p.part === "B" ? "/segments" : p.part === "C" ? "/triage" : "/copilot"}
            data-testid={`part-card-${p.part}`}
            className="group rounded-xl border border-border bg-card p-5 transition-colors duration-200 panel-grid-glow"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-muted-foreground">PART {p.part} · {p.marks} MARKS</span>
              {p.status.includes("PASSED") || p.status.includes("7/7") || p.status.includes("7 scenarios") ? (
                <CircleCheck className="h-4 w-4 text-emerald-400" />
              ) : (
                <CircleAlert className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <h2 className="mt-3 font-heading text-base font-semibold tracking-tight">{p.title}</h2>
            <p className="mt-1 font-mono text-xs text-sky-300">{p.status}</p>
            <ul className="mt-3 space-y-1.5 text-[13px] text-muted-foreground">
              {p.highlights.map((h, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-orange-400">›</span>
                  {h}
                </li>
              ))}
            </ul>
            <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-sky-400">
              Open the part <ArrowRight className="h-3 w-3 transition-transform duration-150 group-hover:translate-x-0.5" />
            </span>
          </Link>
        ))}
        {!data && !isError
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-52 animate-pulse rounded-xl border border-border bg-muted/40" data-testid={`part-card-skeleton-${i}`} />
            ))
          : null}
      </div>
    </div>
  );
}