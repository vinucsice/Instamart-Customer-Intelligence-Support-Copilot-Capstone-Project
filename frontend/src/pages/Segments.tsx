import { useQuery } from "@tanstack/react-query";
import { Crown } from "lucide-react";
import { apiGet } from "@/lib/api";
import type { LapseSection, RetentionRow, SegmentRow, SegmentsSection } from "@/lib/types";
import { Figure, MonoNote, Panel } from "@/components/cx/Panel";
import { dec, inr, num, pct } from "@/lib/format";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { useState } from "react";

export default function Segments() {
  const segments = useQuery({
    queryKey: ["metrics", "segments"],
    queryFn: () => apiGet<{ section: string; data: SegmentsSection }>("/metrics/segments"),
    retry: 1,
  });
  const lapse = useQuery({
    queryKey: ["metrics", "lapse"],
    queryFn: () => apiGet<{ section: string; data: LapseSection }>("/metrics/lapse"),
    retry: 1,
  });
  const customers = useQuery({
    queryKey: ["segments", "customers"],
    queryFn: () => apiGet<SegmentRow[]>("/segments/customers"),
    retry: 1,
  });
  const retention = useQuery({
    queryKey: ["retention"],
    queryFn: () => apiGet<RetentionRow[]>("/retention"),
    retry: 1,
  });
  const [search, setSearch] = useState("");

  const s = segments.data?.data;
  const l = lapse.data?.data;
  const rf = s?.rfm_stats;
  const rows = customers.data ?? [];
  const q = search.trim().toLowerCase();
  const filtered = rows.filter(
    (r) => !q || r.customer_id.toLowerCase().includes(q) || r.segment_name.toLowerCase().includes(q),
  );

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-400">Part B · 28 marks</p>
        <h1 className="mt-1 font-heading text-2xl font-semibold tracking-tight">Segments &amp; lapse prediction</h1>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel
          title="RFM & K-means"
          subtitle={rf ? `${num(rf.customers)} customers · snapshot 2025-10-01` : "…"}
          testid="panel-kmeans"
        >
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Figure label="recency median" value={rf ? `${num(rf.recency_median)} d` : "—"} testid="figure-rfm-recency" />
            <Figure label="frequency mean" value={rf ? dec(rf.frequency_mean) : "—"} testid="figure-rfm-frequency" />
            <Figure label="monetary mean" value={rf ? inr(rf.monetary_mean) : "—"} testid="figure-rfm-monetary" />
            <Figure label="monetary max" value={rf ? inr(rf.monetary_max) : "—"} testid="figure-rfm-max" />
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>K</TableHead>
                <TableHead className="text-right">inertia</TableHead>
                <TableHead className="text-right">silhouette</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(s?.kmeans_table ?? []).map((r) => (
                <TableRow key={r.k} data-testid={`kmeans-row-${r.k}`} className={s?.chosen_k === r.k ? "bg-primary/10" : ""}>
                  <TableCell className="font-mono text-xs">
                    {r.k}
                    {s?.chosen_k === r.k ? <span className="ml-2 rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">chosen</span> : null}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">{num(r.inertia)}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{dec(r.silhouette, 3)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="mt-3 text-xs text-muted-foreground" data-testid="kmeans-reason">{s?.chosen_k_reason}</p>
          <p className="mt-2 text-xs text-muted-foreground" data-testid="kmeans-inertia-note">{s?.k_lower_inertia_cannot_pick}</p>
          <p className="mt-3 font-mono text-[11px] text-sky-300" data-testid="pca-note">
            PCA(2) explained variance: {s?.pca_explained_variance_ratio.map((v) => dec(v, 3)).join(" + ")} = {s ? dec(s.pca_total, 3) : "—"} · cluster ids are labels with no ordering
          </p>
        </Panel>

        <Panel title="Named segments" subtitle="Premium = highest mean monetary value" testid="panel-segment-profiles">
          <div className="space-y-3">
            {(s?.segments_profile ?? []).map((p) => (
              <div
                key={p.segment_id}
                data-testid={`segment-card-${p.segment_id}`}
                className={`rounded-lg border p-3.5 ${p.is_premium ? "border-orange-400/50 bg-[#3b1d04]/30" : "border-border bg-muted/30"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 font-heading text-sm font-semibold">
                    {p.is_premium ? <Crown className="h-3.5 w-3.5 text-orange-400" /> : null}
                    {p.segment_name}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">{num(p.size)} customers</span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 font-mono text-[11px] text-muted-foreground">
                  <span>R {dec(p.recency_mean, 1)} d</span>
                  <span>F {dec(p.frequency_mean, 1)}</span>
                  <span className="text-orange-400">M {inr(p.monetary_mean)}</span>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{p.recommended_action}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Lapse model card" subtitle={`cutoff 2025-09-01 · ${l ? num(l.cohort_customers) : "—"} customers · ${l ? pct(l.lapsed_pct) : "—"} lapsed`} testid="panel-lapse">
        {l ? (
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="rounded-lg border border-border bg-muted/30 p-3.5" data-testid="lapse-baseline">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Baseline (always "not lapsed")</p>
                <p className="mt-2 font-mono text-lg">accuracy {pct(l.baseline.accuracy * 100)}</p>
                <p className="font-mono text-xs text-rose-400">lapsed F1 {dec(l.baseline.f1_lapsed, 1)}</p>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3.5" data-testid="lapse-logreg">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Logistic regression</p>
                <p className="mt-2 font-mono text-xs">C = {l.logistic_regression.best_params.C} · cv F1 {dec(l.logistic_regression.best_cv_f1, 3)}</p>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  test P {dec(l.logistic_regression.test.precision, 3)} · R {dec(l.logistic_regression.test.recall, 3)} · F1 {dec(l.logistic_regression.test.f1, 3)}
                </p>
              </div>
              <div className={`rounded-lg border p-3.5 ${l.selected_model === "random_forest" ? "border-emerald-400/50 bg-emerald-400/5" : "border-border bg-muted/30"}`} data-testid="lapse-rf">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Random forest {l.selected_model === "random_forest" ? "· selected" : ""}</p>
                <p className="mt-2 font-mono text-xs">depth {l.random_forest.best_params.max_depth} · leaf {l.random_forest.best_params.min_samples_leaf} · cv F1 {dec(l.random_forest.best_cv_f1, 3)}</p>
                <p className="mt-1 font-mono text-xs text-emerald-300">
                  test P {dec(l.random_forest.test.precision, 3)} · R {dec(l.random_forest.test.recall, 3)} · F1 {dec(l.random_forest.test.f1, 3)}
                </p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div data-testid="lapse-importances">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Top-5 random-forest importances</p>
                <ul className="mt-2 space-y-1.5">
                  {l.top5_importances.map((f) => (
                    <li key={f.feature} className="flex items-center gap-3 text-xs">
                      <span className="w-44 shrink-0 font-mono">{f.feature}</span>
                      <span className="h-1.5 flex-1 rounded bg-muted">
                        <span className="block h-1.5 rounded bg-sky-400" style={{ width: `${(f.importance / l.top5_importances[0].importance) * 100}%` }} />
                      </span>
                      <span className="w-14 text-right font-mono text-muted-foreground">{dec(f.importance, 3)}</span>
                    </li>
                  ))}
                </ul>
                <ul className="mt-3 space-y-1 text-xs text-muted-foreground" data-testid="lapse-lr-signs">
                  {l.lr_signs.map((c) => (
                    <li key={c.feature}>
                      LR {c.feature}: {c.sign} ({dec(c.coefficient, 3)}) —{" "}
                      {c.feature === "recency" ? "staler customers lapse more" : c.feature === "frequency" ? "more orders, less lapse" : "higher spend slightly raises lapse odds once frequency is controlled"}
                    </li>
                  ))}
                </ul>
              </div>
              <div data-testid="lapse-balance">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Class-balance experiment (logistic regression)</p>
                <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-xs">
                  <div className="rounded-md border border-border bg-[#070a0f] p-2.5">
                    <p className="text-[10px] uppercase text-muted-foreground">un-balanced</p>
                    <p className="mt-1">P {dec(l.balanced_experiment.unbalanced_lr_test.precision, 3)}</p>
                    <p>R {dec(l.balanced_experiment.unbalanced_lr_test.recall, 3)}</p>
                    <p>F1 {dec(l.balanced_experiment.unbalanced_lr_test.f1, 3)}</p>
                  </div>
                  <div className="rounded-md border border-amber-400/40 bg-[#070a0f] p-2.5">
                    <p className="text-[10px] uppercase text-amber-400">oversampled {l.balanced_train.per_class}/{l.balanced_train.per_class}</p>
                    <p className="mt-1">P {dec(l.balanced_experiment.balanced_lr_test.precision, 3)}</p>
                    <p className="text-amber-300">R {dec(l.balanced_experiment.balanced_lr_test.recall, 3)}</p>
                    <p>F1 {dec(l.balanced_experiment.balanced_lr_test.f1, 3)}</p>
                  </div>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">{l.balanced_experiment.reading}</p>
                <p className="mt-2 font-mono text-[11px] text-sky-300">
                  scaler learned mean of frequency {dec(l.scaler_means.learned_frequency_mean_train_only, 3)} vs full cohort{" "}
                  {dec(l.scaler_means.full_cohort_frequency_mean, 3)} — {l.scaler_means.why_differ}
                </p>
              </div>
            </div>

            <p className="mt-4 text-xs text-muted-foreground" data-testid="lapse-leakage">{l.leakage_statement}</p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Lapse metrics appear once the pipeline outputs exist.</p>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Premium retention watch-list" subtitle={`${retention.data?.length ?? 0} highest-risk premium test customers · ${l ? num(l.retention_truly_lapsed) : "—"} truly lapsed`} testid="panel-retention">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>customer</TableHead>
                <TableHead className="text-right">lapse probability</TableHead>
                <TableHead className="text-right">actually lapsed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(retention.data ?? []).map((r) => (
                <TableRow key={r.customer_id}>
                  <TableCell className="font-mono text-xs">{r.customer_id}</TableCell>
                  <TableCell className="text-right font-mono text-xs text-orange-400">{dec(r.lapse_probability, 4)}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{r.actually_lapsed ? "yes" : "no"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="mt-3 text-xs text-muted-foreground" data-testid="retention-caveat">{l?.retention_caveat}</p>
        </Panel>

        <Panel title="Segment explorer" subtitle={`${num(rows.length)} customers — search by id or segment`} testid="panel-segment-explorer">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="C0082 or Premium…"
            data-testid="segment-explorer-search-input"
            className="mb-3"
          />
          <div className="max-h-96 overflow-y-auto rounded-lg border border-border">
            <Table>
              <TableHeader className="sticky top-0 bg-card">
                <TableRow>
                  <TableHead>customer</TableHead>
                  <TableHead>segment</TableHead>
                  <TableHead className="text-right">R / F / M</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.slice(0, 100).map((r) => (
                  <TableRow key={r.customer_id} data-testid={`segment-row-${r.customer_id}`}>
                    <TableCell className="font-mono text-xs">
                      {r.customer_id}
                      {r.is_premium ? <Crown className="ml-1.5 inline h-3 w-3 text-orange-400" /> : null}
                    </TableCell>
                    <TableCell className="text-xs">{r.segment_name}</TableCell>
                    <TableCell className="text-right font-mono text-[11px] text-muted-foreground">
                      {num(r.recency)} / {num(r.frequency)} / {inr(r.monetary)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground" data-testid="segment-explorer-count">
            showing {Math.min(filtered.length, 100)} of {num(filtered.length)} matching · {num(rows.length)} total
          </p>
        </Panel>
      </div>
    </div>
  );
}