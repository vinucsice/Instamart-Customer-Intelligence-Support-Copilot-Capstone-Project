// Hand-written TS mirrors of the backend's Pydantic models (backend/models/capstone.py)
// and of the pipeline's outputs/metrics.json sections. When you change one side, change the
// other in the same edit — nothing infers across the Python boundary.

// ---------------------------------------------------------------- overview
export interface Totals {
  customers: number;
  products: number;
  raw_order_rows: number;
  clean_order_rows: number;
  completed_orders: number;
  completed_revenue_inr: number;
  tickets: number;
  policy_docs: number;
  segmented_customers: number;
}

export interface PartStatus {
  part: string;
  title: string;
  marks: number;
  status: string;
  highlights: string[];
}

export interface OverviewResponse {
  totals: Totals;
  parts: PartStatus[];
}

// ---------------------------------------------------------------- metrics passthrough
export interface SectionResponse {
  section: string;
  data: Record<string, unknown>;
}

// ---------------------------------------------------------------- part A
export interface ColumnMissing {
  column: string;
  dtype: string;
  missing: number;
  missing_pct: number;
}

export interface AuditTable {
  table: string;
  rows: number;
  columns: number;
  column_missing: ColumnMissing[];
}

export interface AuditFigures {
  raw_order_rows: number;
  exact_duplicate_rows: number;
  pending_rows: number;
  distinct_order_ids: number;
  non_numeric_amounts: number;
  negative_delivery_minutes: number;
  blank_delivery_minutes: number;
  blank_ages: number;
  ages_outside_10_100: number;
  raw_city_spellings: number;
  raw_gender_spellings: number;
  blank_genders: number;
}

export interface AuditSection {
  figures: AuditFigures;
  tables: AuditTable[];
}

export interface CleaningRule {
  step: number;
  rule: string;
  changed: number;
  of_which_out_of_range?: number;
}

export interface CleaningSection {
  customers_rules: CleaningRule[];
  orders_rules: CleaningRule[];
  city_counts: Record<string, number>;
  gender_counts: Record<string, number>;
  age_min: number;
  age_max: number;
  missing_ages: number;
  after: Record<string, number>;
}

export interface SqlTopCity {
  city: string;
  customer_id: string;
  total_spend: number;
}

export interface SqlSection {
  q1_customers: number;
  q2_rows: number;
  q2_total: number;
  q2_max_cell: { city: string; category: string; revenue: number };
  q3_products: number;
  q4_customers: number;
  q5_customers: number;
  q5_average: number;
  q6_top_per_city: SqlTopCity[];
  q6_rank_ne_row_number: number;
  q7_days: number;
  q7_last_cumulative: number;
  all_queries_match_references: boolean;
  failures: string[];
}

export interface EdaSection {
  pivot_grand_total: number;
  sql_total_matches_pivot: boolean;
  per_city_named_agg: { city: string; sum: number; mean: number; count: number }[];
  distribution: {
    mean: number;
    median: number;
    skewness: number;
    q1: number;
    q3: number;
    iqr: number;
    lower_fence: number;
    upper_fence: number;
    outliers_below: number;
    outliers_above: number;
  };
  correlation_matrix: Record<string, Record<string, number>>;
  largest_correlation: { pair: string[]; value: number };
  answers_max_200_words: string;
  answers_word_count: number;
}

// ---------------------------------------------------------------- part B
export interface KmeansRow {
  k: number;
  inertia: number;
  silhouette: number;
}

export interface SegmentProfileRow {
  segment_id: number;
  segment_name: string;
  recommended_action: string;
  size: number;
  recency_mean: number;
  frequency_mean: number;
  monetary_mean: number;
  is_premium: boolean;
}

export interface RfmStats {
  customers: number;
  recency_median: number;
  recency_min: number;
  recency_max: number;
  frequency_mean: number;
  frequency_max: number;
  monetary_mean: number;
  monetary_max: number;
}

export interface SegmentsSection {
  rfm_stats: RfmStats;
  kmeans_table: KmeansRow[];
  chosen_k: number;
  chosen_k_reason: string;
  k_lower_inertia_cannot_pick: string;
  segments_profile: SegmentProfileRow[];
  pca_explained_variance_ratio: number[];
  pca_total: number;
}

export interface MetricsRow {
  precision: number;
  recall: number;
  f1: number;
  confusion_matrix: number[][];
}

export interface LapseSection {
  cohort_customers: number;
  lapsed: number;
  lapsed_pct: number;
  train_rows: number;
  test_rows: number;
  baseline: { accuracy: number; f1_lapsed: number };
  logistic_regression: { best_params: { C: number }; best_cv_f1: number; test: MetricsRow };
  random_forest: { best_params: { max_depth: number; min_samples_leaf: number }; best_cv_f1: number; test: MetricsRow };
  selected_model: string;
  selected_test: MetricsRow;
  balanced_train: { rows: number; per_class: number };
  balanced_experiment: {
    model: string;
    unbalanced_lr_test: MetricsRow;
    balanced_lr_test: MetricsRow;
    reading: string;
  };
  top5_importances: { feature: string; importance: number }[];
  lr_signs: { feature: string; coefficient: number; sign: string }[];
  scaler_means: {
    learned_frequency_mean_train_only: number;
    full_cohort_frequency_mean: number;
    why_differ: string;
  };
  retention_list_rows: number;
  retention_truly_lapsed: number;
  leakage_statement: string;
  retention_caveat: string;
}

// ---------------------------------------------------------------- part B lists
export interface SegmentRow {
  customer_id: string;
  recency: number;
  frequency: number;
  monetary: number;
  segment_id: number;
  segment_name: string;
  is_premium: boolean;
}

export interface RetentionRow {
  customer_id: string;
  lapse_probability: number;
  actually_lapsed: number;
}

// ---------------------------------------------------------------- part C
export interface RunStats {
  run_label: string;
  tickets: number;
  statuses: Record<string, number>;
  classified: number;
  accuracy_over_classified: number;
  total_tokens: number;
  tokens_per_classified_ticket: number;
  retries: number;
}

export interface TriageSection {
  tickets_total: number;
  empty_tickets: number;
  long_tickets: number;
  redaction: { email: number; phone: number; order_id: number; total: number; left_after: number };
  retries_per_full_run: number;
  retry_log_sample: string[];
  retry_log_full: string[];
  zero_shot: RunStats;
  few_shot: RunStats;
  confusion_zero_shot: { true: string; predicted: string; n: number }[];
  budget_demo: { budget: number; exhausted: number };
  final_run_statuses: Record<string, number>;
  routing_counts: Record<string, number>;
  priority_counts: Record<string, number>;
  zero_shot_system_prompt: string;
  few_shot_system_prompt: string;
}

export interface TicketRow {
  ticket_id: string;
  customer_id: string;
  status: string;
  category: string;
  segment_name: string;
  priority: string;
  route: string;
  tokens_used: number;
}

// ---------------------------------------------------------------- part D
export interface EvalRow {
  question: string;
  expected_doc: string;
  expected_fact: string;
  sources: string[];
  answer: string;
  doc_hit: boolean | null;
  fact_hit: boolean | null;
  fallback_hit: boolean | null;
}

export interface EvalResult {
  overlap: number;
  doc_hits: number;
  fact_hits: number;
  fallback_hits: number;
  answerable: number;
  unanswerable: number;
  rows: EvalRow[];
  failures: EvalRow[];
}

export interface PolicySection {
  total_chunks: number;
  chunk_counts: Record<string, number>;
  tfidf_explanation: string;
  retrieval_sample: { query: string; sources: string[] };
  eval_overlap10: EvalResult;
  eval_overlap0: EvalResult;
  zero_overlap_reading: string;
}

export interface ToolSpec {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface AgentScenarioRow {
  scenario_id: string;
  status: string;
  final_answer: string;
  llm_calls: number;
  tokens_used: number;
  tools: string[];
  refund_inr: number;
  message: string;
}

export interface AgentSection {
  scenarios: AgentScenarioRow[];
  expected_all_matched: boolean;
  stop_safely: {
    s1_token_limit_200: { status: string; llm_calls: number; tokens_used: number };
    timeout_time_limit_0: { status: string; llm_calls: number };
  };
  crash_resume: { run_id: string; status: string; final_answer: string; tools_in_order: string[]; refund_inr: number };
  react_comparison: string;
  react_comparison_words: number;
  tools_spec: ToolSpec[];
}

// ---------------------------------------------------------------- live copilot
export interface PolicySource {
  source: string;
  score: number;
  text: string;
}

export interface PolicyAskResponse {
  answer: string;
  sources: PolicySource[];
}

export interface AgentStep {
  step: number;
  tool: string;
  arguments: Record<string, unknown>;
  observation: unknown;
}

export interface AgentRunResponse {
  run_id: string;
  scenario_id: string;
  status: string;
  final_answer: string;
  steps: AgentStep[];
  llm_calls: number;
  tokens_used: number;
  tools_executed: string[];
}
