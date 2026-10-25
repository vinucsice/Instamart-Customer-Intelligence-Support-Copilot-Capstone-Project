import { motion } from "motion/react";
import type { AgentStep } from "@/lib/types";

const TOOL_ICON: Record<string, string> = {
  get_order: "DB",
  search_policy: "RAG",
  calculate_refund: "CALC",
  issue_refund: "PAY",
  escalate_to_human: "ESC",
};

export default function AgentTimeline({ steps, testid }: { steps: AgentStep[]; testid?: string }) {
  if (steps.length === 0) return null;
  return (
    <ol data-testid={testid} className="relative ml-3 border-l-2 border-border">
      {steps.map((s, i) => (
        <motion.li
          key={s.step}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: i * 0.08 }}
          className="relative pb-4 pl-5 last:pb-0"
        >
          <span className="absolute -left-[7px] top-1 flex h-3 w-3 items-center justify-center rounded-full bg-sky-400/20">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
          </span>
          <div className="flex items-center gap-2">
            <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-sky-300">
              {TOOL_ICON[s.tool] ?? s.tool}
            </span>
            <span className="font-mono text-xs font-medium">{s.tool}</span>
            <span className="truncate font-mono text-[11px] text-muted-foreground">
              {JSON.stringify(s.arguments)}
            </span>
          </div>
          <pre className="mt-1.5 overflow-x-auto rounded-md border border-border bg-[#070a0f] p-2 font-mono text-[11px] text-emerald-300">
            {JSON.stringify(s.observation)}
          </pre>
        </motion.li>
      ))}
    </ol>
  );
}