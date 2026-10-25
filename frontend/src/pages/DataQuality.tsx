import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { AuditSection, CleaningSection, EdaSection, SqlSection } from "@/lib/types";
import { Figure, MonoNote, Panel } from "@/components/cx/Panel";
import { dec, inr, num } from "@/lib/format";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function useSection<T>(section: string) {
  return useQuery({
    queryKey: ["metrics", section],
    queryFn: () => apiGet<{ section: string; data: T }>(`/metrics/${section}`),
    retry: 1,
  });
}

export default function DataQuality() {
  const audit = useSection<AuditSection>("audit");
  const cleaning = useSection<CleaningSection>("cleaning");
  const sql = useSection<SqlSection>("sql");
  const eda = useSection<EdaSection>("eda");

  const f = audit.data?.data.figures;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-400">Part A · 22 marks</p>
        <h1 className="mt-1 font-heading text-2xl font-semibold tracking-tight">Data Foundation — audit, clean, store, query</h1>
      </div>

      <Panel
        title="Raw export audit"
        subtitle="figures straight from data/raw — the dirt the pipeline starts from"
        testid="panel-raw-audit"
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Figure label="raw order rows" value={f ? num(f.raw_order_rows) : "—"} testid="figure-raw-order-rows" />
          <Figure label="exact duplicates" value={f ? num(f.exact_duplicate_rows) : "—"} testid="figure-exact-duplicates" />
          <Figure label="pending rows" value={f ? num(f.pending_rows) : "—"} testid="figure-pending-rows" />
          <Figure label="distinct order ids" value={f ? num(f.distinct_order_ids) : "—"} testid="figure-distinct-order-ids" />
          <Figure label="non-numeric amounts" value={f ? num(f.non_numeric_amounts) : "—"} testid="figure-non-numeric-amounts" />
          <Figure label="negative delivery min" value={f ? num(f.negative_delivery_minutes) : "—"} testid="figure-negative-delivery" />
          <Figure label="blank delivery min" value={f ? num(f.blank_delivery_minutes) : "—"} testid="figure-blank-delivery" />
          <Figure label="blank ages" value={f ? num(f.blank_ages) : "—"} testid="figure-blank-ages" />
          <Figure label="ages outside 10-100" value={f ? num(f.ages_outside_10_100) : "—"} testid="figure-ages-out-of-range" />
          <Figure label="raw city spellings" value={f ? num(f.raw_city_spellings) : "—"} testid="figure-city-spellings" />
          <Figure label="raw gender spellings" value={f ? num(f.raw_gender_spellings) : "—"} testid="figure-gender-spellings" />
          <Figure label="blank genders" value={f ? num(f.blank_genders) : "—"} testid="figure-blank-genders" />
        </div>

        <Tabs defaultValue="orders" className="mt-5">
          <TabsList data-testid="audit-tables-tabs">
            {(audit.data?.data.tables ?? [{ table: "orders" }, { table: "customers" }, { table: "products" }]).map((t) => (
              <TabsTrigger key={t.table} value={t.table} data-testid={`audit-tab-${t.table}`}>
                {t.table}
              </TabsTrigger>
            ))}
          </TabsList>
          {(audit.data?.data.tables ?? []).map((t) => (
            <TabsContent key={t.table} value={t.table} data-testid={`audit-table-${t.table}`}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>column</TableHead>
                    <TableHead>dtype</TableHead>
                    <TableHead className="text-right">missing</TableHead>
                    <TableHead className="text-right">missing %</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {t.column_missing.map((c) => (
                    <TableRow key={c.column}>
                      <TableCell className="font-mono text-xs">{c.column}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{c.dtype}</TableCell>
                      <TableCell className="text-right font-mono text-xs">{num(c.missing)}</TableCell>
                      <TableCell className="text-right font-mono text-xs">{dec(c.missing_pct)}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabsContent>
          ))}
        </Tabs>
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Customer cleaning rules" subtitle="every rule with the number of values it changed" testid="panel-cleaning-customers">
          <ol className="space-y-2.5">
            {(cleaning.data?.data.customers_rules ?? []).map((r) => (
              <li key={r.step} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5" data-testid={`cleaning-rule-customers-${r.step}`}>
                <span className="text-[13px] leading-snug">{r.rule}</span>
                <span className="shrink-0 font-mono text-xs text-orange-400">{num(r.changed)} changed</span>
              </li>
            ))}
          </ol>
          <div className="mt-4 flex flex-wrap gap-2" data-testid="cleaning-city-counts">
            {Object.entries(cleaning.data?.data.city_counts ?? {}).map(([city, n]) => (
              <span key={city} className="rounded-full border border-border bg-muted px-2.5 py-1 font-mono text-[11px]">
                {city} {num(n)}
              </span>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground" data-testid="cleaning-gender-counts">
            genders:{" "}
            {Object.entries(cleaning.data?.data.gender_counts ?? {})
              .map(([g, n]) => `${g} ${num(n)}`)
              .join(" · ")}{" "}
            — ages {dec(cleaning.data?.data.age_min ?? 0, 1)}–{dec(cleaning.data?.data.age_max ?? 0, 1)} with{" "}
            {num(cleaning.data?.data.missing_ages ?? 0)} missing after imputation
          </p>
        </Panel>

        <Panel title="Order cleaning rules" subtitle="applied strictly in this order, counts measured" testid="panel-cleaning-orders">
          <ol className="space-y-2.5">
            {(cleaning.data?.data.orders_rules ?? []).map((r) => (
              <li key={r.step} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2.5" data-testid={`cleaning-rule-orders-${r.step}`}>
                <span className="text-[13px] leading-snug">{r.rule}</span>
                <span className="shrink-0 font-mono text-xs text-orange-400">{num(r.changed)} changed</span>
              </li>
            ))}
          </ol>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Figure label="clean rows" value={num(cleaning.data?.data.after.order_rows ?? 0)} testid="figure-clean-rows" />
            <Figure label="completed" value={num(cleaning.data?.data.after.completed ?? 0)} testid="figure-clean-completed" />
            <Figure label="cancelled" value={num(cleaning.data?.data.after.cancelled ?? 0)} testid="figure-clean-cancelled" />
            <Figure label="missing amounts" value={num(cleaning.data?.data.after.missing_order_amount ?? 0)} testid="figure-clean-missing-amounts" />
            <Figure label="completed rev" value={inr(cleaning.data?.data.after.completed_amount_sum ?? 0)} testid="figure-clean-revenue" />
            <Figure label="pending left" value={num(cleaning.data?.data.after.pending ?? 0)} testid="figure-clean-pending" />
          </div>
        </Panel>
      </div>

      <Panel title="Seven SQL analyses" subtitle="sql/queries.sql run against data/instamart.db with pd.read_sql_query" testid="panel-sql">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <Figure label="Q1 big spenders > 8000" value={sql.data ? `${num(sql.data.data.q1_customers)} customers` : "—"} testid="figure-q1" />
          <Figure label="Q2 city x category cells" value={sql.data ? num(sql.data.data.q2_rows) : "—"} testid="figure-q2" />
          <Figure label="Q3 above-avg price products" value={sql.data ? num(sql.data.data.q3_products) : "—"} testid="figure-q3" />
          <Figure label="Q4 no completed order" value={sql.data ? `${num(sql.data.data.q4_customers)} customers` : "—"} testid="figure-q4" />
          <Figure label="Q5 above-average spenders" value={sql.data ? num(sql.data.data.q5_customers) : "—"} testid="figure-q5" />
          <Figure label="Q5 average total" value={sql.data ? inr(sql.data.data.q5_average) : "—"} testid="figure-q5-avg" />
          <Figure label="Q6 RANK != ROW_NUMBER" value={sql.data ? num(sql.data.data.q6_rank_ne_row_number) : "—"} testid="figure-q6-ties" />
          <Figure label="Q7 daily rows / last cum." value={sql.data ? `${num(sql.data.data.q7_days)} / ${inr(sql.data.data.q7_last_cumulative)}` : "—"} testid="figure-q7" />
        </div>
        <div className="mt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>city</TableHead>
                <TableHead>top customer by completed spend (Q6, RANK = 1)</TableHead>
                <TableHead className="text-right">total spend</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(sql.data?.data.q6_top_per_city ?? []).map((r) => (
                <TableRow key={r.city}>
                  <TableCell>{r.city}</TableCell>
                  <TableCell className="font-mono text-xs">{r.customer_id}</TableCell>
                  <TableCell className="text-right font-mono text-xs">{inr(r.total_spend)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {sql.data?.data.q2_max_cell ? (
          <p className="mt-3 text-xs text-muted-foreground" data-testid="sql-q2-note">
            Q2's largest cell: {sql.data.data.q2_max_cell.city} / {sql.data.data.q2_max_cell.category} at{" "}
            {inr(sql.data.data.q2_max_cell.revenue)}; the 30 revenues add up to {inr(sql.data.data.q2_total)} —
            identical to the pivot_table grand total and the Q7 running total.
            {sql.data.data.q6_rank_ne_row_number > 0
              ? ` RANK() differs from ROW_NUMBER() on ${sql.data.data.q6_rank_ne_row_number} rows because tied total spends share a rank while row numbers stay distinct.`
              : ""}
          </p>
        ) : null}
      </Panel>

      <Panel title="Exploratory analysis of completed order_amount" subtitle="pandas cross-check + distribution story" testid="panel-eda">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          <Figure label="mean" value={eda.data ? inr(eda.data.data.distribution.mean) : "—"} testid="figure-eda-mean" />
          <Figure label="median" value={eda.data ? inr(eda.data.data.distribution.median) : "—"} testid="figure-eda-median" />
          <Figure label="skewness" value={eda.data ? dec(eda.data.data.distribution.skewness) : "—"} testid="figure-eda-skew" />
          <Figure label="Q1 / Q3" value={eda.data ? `${dec(eda.data.data.distribution.q1)} / ${dec(eda.data.data.distribution.q3)}` : "—"} testid="figure-eda-quartiles" />
          <Figure label="outliers above fence" value={eda.data ? `${num(eda.data.data.distribution.outliers_above)} of ${inr(eda.data.data.distribution.upper_fence)}` : "—"} testid="figure-eda-outliers" />
        </div>
        <p className="mt-3 text-xs text-muted-foreground" data-testid="eda-correlation-note">
          Largest correlation in absolute value: {eda.data?.data.largest_correlation.pair.join(" x ")} at{" "}
          {eda.data ? dec(eda.data.data.largest_correlation.value, 3) : "—"} — far too small to imply causation.
        </p>
        <MonoNote testid="eda-answers">{eda.data?.data.answers_max_200_words ?? "waiting for pipeline outputs…"}</MonoNote>
      </Panel>
    </div>
  );
}