import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Loader2, Send, Play } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost } from "@/lib/api";
import type { AgentRunResponse, AgentSection, PolicyAskResponse, PolicySection } from "@/lib/types";
import AgentTimeline from "@/components/cx/AgentTimeline";
import { Figure, MonoNote, Panel } from "@/components/cx/Panel";
import { dec, inr, num } from "@/lib/format";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const SAMPLE_QUESTIONS = [
  "What delivery time makes a completed order eligible for a full refund?",
  "Who must approve a refund above INR 1000?",
  "Is cash on delivery available for a large order?",
  "Who won the cricket world cup final?",
];

export default function Copilot() {
  const policy = useQuery({
    queryKey: ["metrics", "policy"],
    queryFn: () => apiGet<{ section: string; data: PolicySection }>("/metrics/policy"),
    retry: 1,
  });
  const agent = useQuery({
    queryKey: ["metrics", "agent"],
    queryFn: () => apiGet<{ section: string; data: AgentSection }>("/metrics/agent"),
    retry: 1,
  });
  const scenarios = useQuery({
    queryKey: ["agent", "scenarios"],
    queryFn: () => apiGet<AgentRunResponse[]>("/agent/scenarios"),
    retry: 1,
  });

  const [question, setQuestion] = useState("");
  const [message, setMessage] = useState("");
  const ask = useMutation({
    mutationFn: (q: string) => apiPost<PolicyAskResponse>("/policy/ask", { question: q }),
    onSuccess: () => toast.success("policy assistant answered"),
    onError: (e) => toast.error(`ask failed: ${e.message}`),
  });
  const run = useMutation({
    mutationFn: (m: string) => apiPost<AgentRunResponse>("/agent/run", { message: m }),
    onSuccess: () => toast.success("agent run finished"),
    onError: (e) => toast.error(`agent run failed: ${e.message}`),
  });

  const p = policy.data?.data;
  const a = agent.data?.data;
  const asked = ask.data;
  const ran = run.data;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-orange-400">Part D · 28 marks</p>
        <h1 className="mt-1 font-heading text-2xl font-semibold tracking-tight">Policy assistant &amp; refund agent</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Both run the real pipeline code with the offline mock LLM — no key, no network, live in your browser session.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel title="Grounded policy Q&A" subtitle={`TF-IDF over ${p ? num(p.total_chunks) : "—"} chunks · 3 chunks per answer`} testid="panel-policy-qa">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (question.trim()) ask.mutate(question.trim());
            }}
          >
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a policy question…"
              data-testid="policy-question-input"
            />
            <Button type="submit" disabled={ask.isPending} data-testid="policy-ask-submit-btn">
              {ask.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Ask
            </Button>
          </form>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {SAMPLE_QUESTIONS.map((s) => (
              <button
                key={s}
                data-testid={`policy-sample-question-${SAMPLE_QUESTIONS.indexOf(s) + 1}`}
                onClick={() => { setQuestion(s); ask.mutate(s); }}
                className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition-colors duration-150 hover:border-sky-400/50 hover:text-sky-300"
              >
                {s.length > 44 ? `${s.slice(0, 44)}…` : s}
              </button>
            ))}
          </div>

          {asked ? (
            <div className="mt-4 space-y-3" data-testid="policy-answer-block">
              <div className="rounded-lg border border-emerald-400/30 bg-emerald-400/5 p-3.5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-400">answer</p>
                <p className="mt-1.5 text-sm leading-relaxed" data-testid="policy-answer-text">{asked.answer}</p>
              </div>
              <div className="space-y-2">
                {asked.sources.map((src, i) => (
                  <div key={i} className="rounded-lg border border-border bg-muted/30 p-3" data-testid={`policy-source-${i + 1}`}>
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="font-mono text-[10px]">{src.source}</Badge>
                      <span className="font-mono text-[11px] text-sky-300">cos {dec(src.score, 4)}</span>
                    </div>
                    <p className="mt-2 font-mono text-[11px] leading-relaxed text-muted-foreground">{src.text}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-xs text-muted-foreground" data-testid="policy-answer-empty">
              Ask anything — unanswerable questions get the grounded fallback ("I could not find…"), never a guess.
            </p>
          )}
        </Panel>

        <Panel title="Refund agent runner" subtitle="five tools, ReAct loop, stop-safely limits — live" testid="panel-agent-runner">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (message.trim()) run.mutate(message.trim());
            }}
          >
            <Input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="My order ORD-100048 reached me very late. I would like a refund."
              data-testid="agent-message-input"
            />
            <Button type="submit" disabled={run.isPending} data-testid="agent-run-submit-btn">
              {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run
            </Button>
          </form>

          {ran ? (
            <div className="mt-4 space-y-3" data-testid="agent-run-block">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 font-mono text-xs ${ran.status === "REFUND" ? "bg-emerald-400/10 text-emerald-300" : "bg-muted text-muted-foreground"}`} data-testid="agent-run-status">
                  {ran.status}
                </span>
                <span className="font-mono text-xs text-muted-foreground" data-testid="agent-run-telemetry">
                  {ran.llm_calls} model calls · {num(ran.tokens_used)} tokens · {ran.steps.length} tool steps
                </span>
              </div>
              <AgentTimeline steps={ran.steps} testid="agent-run-timeline" />
              <div className="rounded-lg border border-sky-400/30 bg-sky-400/5 p-3">
                <p className="font-mono text-xs text-sky-300" data-testid="agent-run-final">{ran.final_answer}</p>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-xs text-muted-foreground" data-testid="agent-run-empty">
              Type a request (or replay a benchmark scenario below) and the agent will look up the order in
              data/instamart.db, search the policies, calculate and issue or escalate the refund.
            </p>
          )}
        </Panel>
      </div>

      <Panel
        title="Benchmark: the seven refund scenarios"
        subtitle="outputs/agent_runs.jsonl — one click replays each request through the live agent"
        testid="panel-scenarios"
      >
        <div className="mb-4 flex flex-wrap gap-2">
          {(a?.scenarios ?? []).map((s, i) => (
            <Button
              key={s.scenario_id}
              variant="outline"
              size="sm"
              data-testid={`run-scenario-btn-${i + 1}`}
              onClick={() => {
                setMessage(s.message);
                run.mutate(s.message);
              }}
            >
              {s.scenario_id}: {s.status}
            </Button>
          ))}
        </div>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-3 py-2">scenario</th>
                <th className="px-3 py-2">status</th>
                <th className="px-3 py-2">refund</th>
                <th className="px-3 py-2">model calls</th>
                <th className="px-3 py-2">tokens</th>
                <th className="px-3 py-2">final answer</th>
              </tr>
            </thead>
            <tbody className="font-mono" data-testid="scenarios-table">
              {(a?.scenarios ?? []).map((s) => (
                <tr key={s.scenario_id} className="border-t border-border">
                  <td className="px-3 py-2">{s.scenario_id}</td>
                  <td className={`px-3 py-2 ${s.status.startsWith("FALLBACK") ? "text-amber-300" : "text-emerald-300"}`}>{s.status}</td>
                  <td className="px-3 py-2">{s.refund_inr ? inr(s.refund_inr) : "—"}</td>
                  <td className="px-3 py-2">{s.llm_calls}</td>
                  <td className="px-3 py-2">{num(s.tokens_used)}</td>
                  <td className="px-3 py-2 text-muted-foreground">{s.final_answer}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {a ? (
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-border bg-muted/30 p-3.5" data-testid="stop-safely-panel">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Stop-safely demos</p>
              <p className="mt-2 font-mono text-xs">S1 @ token_limit 200 → <span className="text-amber-300">{a.stop_safely.s1_token_limit_200.status}</span> ({a.stop_safely.s1_token_limit_200.llm_calls} calls, {num(a.stop_safely.s1_token_limit_200.tokens_used)} tok)</p>
              <p className="font-mono text-xs">time_limit 0 → <span className="text-amber-300">{a.stop_safely.timeout_time_limit_0.status}</span> ({a.stop_safely.timeout_time_limit_0.llm_calls} calls)</p>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-3.5" data-testid="crash-resume-panel">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Crash &amp; resume (S1)</p>
              <p className="mt-2 font-mono text-xs">{a.crash_resume.status} · {inr(a.crash_resume.refund_inr)}</p>
              <p className="mt-1 font-mono text-[11px] text-sky-300">{a.crash_resume.tools_in_order.join(" → ")}</p>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-3.5" data-testid="tools-panel">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Tools</p>
              <ul className="mt-2 space-y-1 font-mono text-[11px] text-muted-foreground">
                {(a.tools_spec ?? []).map((t) => (
                  <li key={t.name}><span className="text-sky-300">{t.name}</span> — {t.description}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}

        {a ? (
          <div className="mt-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">ReAct vs plan-and-execute ({a.react_comparison_words} words)</p>
            <MonoNote testid="react-comparison">{a.react_comparison}</MonoNote>
          </div>
        ) : null}
      </Panel>

      <Panel
        title="Retrieval & grounding evaluation"
        subtitle={`overlap ${p?.eval_overlap10.overlap ?? 10} vs zero overlap — the failure mode made visible`}
        testid="panel-policy-eval"
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Figure label="docs in top-3" value={p ? `${p.eval_overlap10.doc_hits}/12` : "—"} testid="figure-eval-docs" />
          <Figure label="facts in answer" value={p ? `${p.eval_overlap10.fact_hits}/12` : "—"} testid="figure-eval-facts" />
          <Figure label="fallback (unanswerable)" value={p ? `${p.eval_overlap10.fallback_hits}/2` : "—"} testid="figure-eval-fallback" />
          <Figure label="zero-overlap failures" value={p ? num(p.eval_overlap0.failures.length) : "—"} testid="figure-eval-zerofail" />
        </div>
        <p className="mt-3 text-xs text-muted-foreground" data-testid="tfidf-explanation">{p?.tfidf_explanation}</p>
        <p className="mt-2 text-xs text-muted-foreground" data-testid="zero-overlap-note">
          {p?.zero_overlap_reading}
          {p && p.eval_overlap0.failures.length > 0
            ? ` Broken with zero overlap: "${p.eval_overlap0.failures[0].question}" — the expected fact "${p.eval_overlap0.failures[0].expected_fact}" sits in a sentence that straddles a chunk boundary.`
            : ""}
        </p>
        <MonoNote testid="policy-chunk-counts">
          {p ? Object.entries(p.chunk_counts).map(([k, v]) => `${k}: ${v}`).join("  ·  ") : "chunks…"}
        </MonoNote>
      </Panel>
    </div>
  );
}