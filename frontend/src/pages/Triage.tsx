import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { apiGet } from "@/lib/api";
import type { TicketRow, TriageSection } from "@/lib/types";
import { Figure, MonoNote, Panel, PriorityBadge, RouteBadge } from "@/components/cx/Panel";
import { dec, num } from "@/lib/format";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";

const ROUTES = ["all", "security_team", "premium_desk", "support_queue", "human_review"] as const;

export default function Triage() {
  const stats = useQuery({
    queryKey: ["metrics", "triage"],
    queryFn: () => apiGet<{ section: string; data: TriageSection }>("/metrics/triage"),
    retry: 1,
  });
  const tickets = useQuery({
    queryKey: ["triage", "tickets"],
    queryFn: () => apiGet<TicketRow[]>("/triage/tickets"),
    retry: 1,
  });
  const [routeFilter, setRouteFilter] = useState<(typeof ROUTES)[number]>("all");
  const [search, setSearch] = useState("");

  const t = stats.data?.data;
  const rows = tickets.data ?? [];
  const q = search.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          (routeFilter === "all" || r.route === routeFilter) &&
          (!q || r.ticket_id.toLowerCase().includes(q) || r.customer_id.toLowerCase().includes(q) || r.category.includes(q)),
      ),
    [rows, routeFilter, q],
  );

  const zs = t?.zero_shot;
  const fs = t?.few_shot;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-400">Part C · 22 marks</p>
        <h1 className="mt-1 font-heading text-2xl font-semibold tracking-tight">Ticket triage with guardrails</h1>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6" data-testid="triage-funnel">
        <Figure label="tickets in" value={t ? num(t.tickets_total) : "—"} testid="figure-triage-total" />
        <Figure label="skipped (empty)" value={t ? num(t.final_run_statuses?.skipped_empty ?? 0) : "—"} testid="figure-triage-empty" />
        <Figure label="flagged (long)" value={t ? num(t.final_run_statuses?.flagged_long ?? 0) : "—"} testid="figure-triage-long" />
        <Figure label="sent to model" value={t ? num(t.tickets_total - (t.final_run_statuses?.skipped_empty ?? 0) - (t.final_run_statuses?.flagged_long ?? 0)) : "—"} testid="figure-triage-eligible" />
        <Figure label="flagged (invalid JSON)" value={t ? num(t.final_run_statuses?.flagged_invalid_output ?? 0) : "—"} testid="figure-triage-invalid" />
        <Figure label="retries recovered" value={t ? num(t.retries_per_full_run) : "—"} testid="figure-triage-retries" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel title="Privacy redaction proof" subtitle="applied before any prompt is built" testid="panel-redaction">
          <div className="flex items-center gap-2 text-emerald-400">
            <ShieldCheck className="h-4 w-4" />
            <span className="text-xs" data-testid="redaction-verify-note">re-running the patterns on redacted text finds 0 leftovers (asserted in code)</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Figure label="emails -> [EMAIL]" value={t ? num(t.redaction.email) : "—"} testid="figure-redaction-email" />
            <Figure label="phones -> [PHONE]" value={t ? num(t.redaction.phone) : "—"} testid="figure-redaction-phone" />
            <Figure label="order ids -> [ORDER_ID]" value={t ? num(t.redaction.order_id) : "—"} testid="figure-redaction-order" />
            <Figure label="total substitutions" value={t ? num(t.redaction.total) : "—"} testid="figure-redaction-total" />
          </div>
          <MonoNote testid="redaction-log-sample">{t?.retry_log_full?.slice(0, 2).join("\n") ?? "retry log…"}</MonoNote>
        </Panel>

        <Panel title="Zero-shot vs few-shot" subtitle="same 156 eligible tickets, mock_llm CLASSIFY marker" testid="panel-zero-vs-few">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-muted/30 p-3" data-testid="zero-shot-card">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">zero-shot</p>
              <p className="mt-2 font-mono text-xl text-sky-300">{zs ? `${dec(zs.accuracy_over_classified, 1)}%` : "—"}</p>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">{zs ? `${num(zs.classified)} classified · ${num(zs.total_tokens)} tok · ${dec(zs.tokens_per_classified_ticket, 1)} tok/ticket` : ""}</p>
            </div>
            <div className="rounded-lg border border-emerald-400/40 bg-emerald-400/5 p-3" data-testid="few-shot-card">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">few-shot</p>
              <p className="mt-2 font-mono text-xl text-emerald-300">{fs ? `${dec(fs.accuracy_over_classified, 1)}%` : "—"}</p>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">{fs ? `${num(fs.classified)} classified · ${num(fs.total_tokens)} tok · ${dec(fs.tokens_per_classified_ticket, 1)} tok/ticket` : ""}</p>
            </div>
          </div>
          <p className="mt-3 text-xs text-muted-foreground" data-testid="few-shot-worth-note">
            {zs && fs
              ? `The few-shot prompt costs ${dec(fs.tokens_per_classified_ticket - zs.tokens_per_classified_ticket, 1)} extra tokens per ticket (${num(fs.total_tokens)} vs ${num(zs.total_tokens)} total) and buys +${dec(fs.accuracy_over_classified - zs.accuracy_over_classified, 1)} points of accuracy: every zero-shot error is a fraud or technical ticket whose plain words ("charged", "payment") also exist in billing, and the two examples teach the priority that saves it.`
              : "waiting for pipeline outputs…"}
          </p>
        </Panel>

        <Panel title="Token budget" subtitle={`zero-shot demo run, TOKEN_BUDGET = ${t ? num(t.budget_demo.budget) : "—"}`} testid="panel-budget">
          <div className="grid grid-cols-2 gap-3">
            <Figure label="budget exhausted" value={t ? num(t.budget_demo.exhausted) : "—"} sub="tickets routed to human review without a model call" testid="figure-budget-exhausted" />
            <Figure label="final run budget" value="100,000" sub="no ticket exhausted in the final routed run" testid="figure-final-budget" />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Before every model call the running total of usage.total_tokens is compared with the budget; once it
            is reached the ticket is marked budget_exhausted and routed to human review.
          </p>
        </Panel>
      </div>

      <Panel
        title="Routed ticket ledger"
        subtitle={`${num(filtered.length)} of ${num(rows.length)} tickets · filters use the routing rules (segments from Part B)`}
        testid="panel-ticket-ledger"
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {ROUTES.map((r) => (
            <button
              key={r}
              data-testid={`ticket-filter-${r}`}
              onClick={() => setRouteFilter(r)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors duration-150 ${
                routeFilter === r ? "border-sky-400/60 bg-sky-400/10 text-sky-300" : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {r.replace(/_/g, " ")}
              {t && r !== "all" ? ` · ${t.routing_counts[r] ?? 0}` : ""}
            </button>
          ))}
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="T0024 / C0486 / fraud…"
            data-testid="ticket-search-input"
            className="ml-auto w-56"
          />
        </div>
        <div className="max-h-[520px] overflow-y-auto rounded-lg border border-border">
          <Table>
            <TableHeader className="sticky top-0 bg-card">
              <TableRow>
                <TableHead>ticket</TableHead>
                <TableHead>customer</TableHead>
                <TableHead>status</TableHead>
                <TableHead>category</TableHead>
                <TableHead>segment</TableHead>
                <TableHead>priority</TableHead>
                <TableHead>route</TableHead>
                <TableHead className="text-right">tokens</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((r) => (
                <TableRow key={r.ticket_id} data-testid={`ticket-row-${r.ticket_id}`}>
                  <TableCell className="font-mono text-xs">{r.ticket_id}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{r.customer_id}</TableCell>
                  <TableCell className="font-mono text-[11px]">{r.status}</TableCell>
                  <TableCell className="text-xs">{r.category || "—"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{r.segment_name || "—"}</TableCell>
                  <TableCell><PriorityBadge priority={r.priority} testid={`ticket-priority-${r.ticket_id}`} /></TableCell>
                  <TableCell><RouteBadge route={r.route} testid={`ticket-route-${r.ticket_id}`} /></TableCell>
                  <TableCell className="text-right font-mono text-xs">{num(r.tokens_used)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Zero-shot confusion (147 classified)" subtitle="every error is fraud/technical predicted as billing" testid="panel-confusion">
          <div className="grid grid-cols-1 gap-1.5 font-mono text-xs" data-testid="confusion-table">
            {(t?.confusion_zero_shot ?? []).map((c) => (
              <div
                key={`${c.true}-${c.predicted}`}
                className={`flex items-center justify-between rounded border px-3 py-1.5 ${
                  c.true === c.predicted ? "border-emerald-400/30 bg-emerald-400/5" : "border-rose-400/40 bg-rose-400/5"
                }`}
              >
                <span>
                  true <span className="text-foreground">{c.true}</span> → predicted{" "}
                  <span className={c.true === c.predicted ? "text-emerald-300" : "text-rose-300"}>{c.predicted}</span>
                </span>
                <span className="text-muted-foreground">{num(c.n)}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="The two prompts" subtitle="both CLASSIFY + four categories + JSON-only; few-shot adds EXAMPLES:" testid="panel-prompts">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">zero-shot system prompt</p>
          <MonoNote testid="zero-shot-prompt">{t?.zero_shot_system_prompt ?? "…"}</MonoNote>
          <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">few-shot system prompt</p>
          <MonoNote testid="few-shot-prompt">{t?.few_shot_system_prompt ?? "…"}</MonoNote>
        </Panel>
      </div>
    </div>
  );
}