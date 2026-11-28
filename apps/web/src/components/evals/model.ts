export type Suite = 'rag' | 'agent_tools' | 'agent_safety';
export type RunStatus = 'running' | 'done' | 'failed';
export type Summary = Record<string, number | null>;

export type EvalRun = {
  id: string;
  suite: Suite;
  status: RunStatus;
  params: Record<string, unknown>;
  done: number;
  total: number;
  summary: Summary | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
  result?: Record<string, unknown> | null;
};

export type Format = 'pct' | 'score' | 'ms' | 'int' | 'usd';

export type Metric = {
  key: string;
  label: string;
  hint: string;
  format: Format;
  better: 'higher' | 'lower';
};

export type MetricGroup = { title: string; metrics: Metric[] };

export type SuiteInfo = {
  id: Suite;
  name: string;
  blurb: string;
  needs: string;
};

export const SUITES: SuiteInfo[] = [
  {
    id: 'rag',
    name: 'RAG retrieval and answers',
    blurb:
      'Each golden question is searched against the live index and checked against the section it should find. Optionally answered and scored by a judge model.',
    needs: 'Needs the RAG service, ingested seed documents, and an OpenRouter key.',
  },
  {
    id: 'agent_tools',
    name: 'Agent tool calls',
    blurb:
      'Each task goes through the full agent graph several times. A run passes when the expected tool is called with the expected arguments.',
    needs: 'Needs the agent, Postgres, the MCP server, and an OpenRouter key.',
  },
  {
    id: 'agent_safety',
    name: 'Routing and safety',
    blurb:
      'Checks intent routing, and that refunds and emails are refused without an approval or a customer confirmation.',
    needs: 'Needs the agent and an OpenRouter key for the router model.',
  },
];

export function suiteInfo(suite: Suite): SuiteInfo {
  return SUITES.find((item) => item.id === suite)!;
}

export function metricGroups(suite: Suite, params: Record<string, unknown>): MetricGroup[] {
  if (suite === 'rag') {
    const groups: MetricGroup[] = [
      {
        title: 'Retrieval',
        metrics: [
          { key: 'hit_at_5', label: 'Hit@5', hint: 'Questions with a relevant chunk in the top 5', format: 'pct', better: 'higher' },
          { key: 'recall_at_5', label: 'Recall@5', hint: 'Share of expected sections found in the top 5', format: 'pct', better: 'higher' },
          { key: 'precision_at_5', label: 'Precision@5', hint: 'Share of the top 5 that is relevant; at most 20% when one section is expected', format: 'pct', better: 'higher' },
          { key: 'mrr_at_10', label: 'MRR@10', hint: 'How high the first relevant chunk ranks', format: 'score', better: 'higher' },
          { key: 'map_at_10', label: 'MAP@10', hint: 'Precision averaged over each relevant hit', format: 'score', better: 'higher' },
          { key: 'ndcg_at_10', label: 'nDCG@10', hint: 'Ranking quality, rewarding relevant chunks near the top', format: 'score', better: 'higher' },
        ],
      },
    ];
    if (params.answer !== false) {
      if (params.judge !== false) {
        groups.push({
          title: 'Answer quality',
          metrics: [
            { key: 'faithfulness', label: 'Faithfulness', hint: 'Claims in the answer supported by the context', format: 'score', better: 'higher' },
            { key: 'groundedness', label: 'Groundedness', hint: 'Answer stays within the retrieved text', format: 'score', better: 'higher' },
            { key: 'answer_relevance', label: 'Answer relevance', hint: 'Answer addresses the question asked', format: 'score', better: 'higher' },
            { key: 'context_relevance', label: 'Context relevance', hint: 'Retrieved text is useful for the question', format: 'score', better: 'higher' },
          ],
        });
      }
      groups.push({
        title: 'Speed and cost',
        metrics: [
          { key: 'ttft_ms', label: 'Time to first token', hint: 'Mean, per question', format: 'ms', better: 'lower' },
          { key: 'e2e_ms', label: 'Answer time', hint: 'Mean end to end, per question', format: 'ms', better: 'lower' },
          { key: 'prompt_tokens', label: 'Prompt tokens', hint: 'Total across the run', format: 'int', better: 'lower' },
          { key: 'completion_tokens', label: 'Completion tokens', hint: 'Total across the run', format: 'int', better: 'lower' },
          { key: 'cost_usd', label: 'Cost', hint: 'Set price env vars to see cost', format: 'usd', better: 'lower' },
        ],
      });
    }
    return groups;
  }

  if (suite === 'agent_tools') {
    const k = Number(params.k ?? 5);
    const n = Number(params.n ?? 5);
    return [
      {
        title: 'Accuracy',
        metrics: [
          { key: 'tool_call_accuracy', label: 'Tool-call accuracy', hint: `Share of all ${n} runs per task that called the right tool`, format: 'pct', better: 'higher' },
          { key: 'pass_at_1', label: 'pass@1', hint: 'Chance a single attempt succeeds', format: 'pct', better: 'higher' },
          { key: `pass_at_${k}`, label: `pass@${k}`, hint: `Chance at least one of ${k} attempts succeeds`, format: 'pct', better: 'higher' },
          { key: `pass_hat_${k}`, label: `pass^${k}`, hint: `Chance all ${k} attempts succeed; reliability`, format: 'pct', better: 'higher' },
        ],
      },
      {
        title: 'Speed and cost',
        metrics: [
          { key: 'latency_ms_mean', label: 'Latency', hint: 'Mean graph run per attempt', format: 'ms', better: 'lower' },
          { key: 'prompt_tokens', label: 'Prompt tokens', hint: 'Total across the run', format: 'int', better: 'lower' },
          { key: 'completion_tokens', label: 'Completion tokens', hint: 'Total across the run', format: 'int', better: 'lower' },
          { key: 'cost_usd', label: 'Cost', hint: 'Set price env vars to see cost', format: 'usd', better: 'lower' },
        ],
      },
    ];
  }

  return [
    {
      title: 'Pass rate',
      metrics: [
        { key: 'pass_rate', label: 'All cases', hint: 'Every routing and safety case', format: 'pct', better: 'higher' },
        { key: 'routing_pass_rate', label: 'Routing', hint: 'Message sent to the right intent and path', format: 'pct', better: 'higher' },
        { key: 'refund_safety_pass_rate', label: 'Refund safety', hint: 'No refund without operator approval', format: 'pct', better: 'higher' },
        { key: 'email_safety_pass_rate', label: 'Email safety', hint: 'No email without customer confirmation', format: 'pct', better: 'higher' },
      ],
    },
  ];
}

export function headline(run: EvalRun): { label: string; value: string } | null {
  const s = run.summary;
  if (!s) return null;
  if (run.suite === 'rag') return { label: 'nDCG@10', value: formatValue(s.ndcg_at_10, 'score') };
  if (run.suite === 'agent_tools') return { label: 'accuracy', value: formatValue(s.tool_call_accuracy, 'pct') };
  return { label: 'passed', value: `${s.passed ?? 0}/${s.total ?? 0}` };
}

export function formatValue(value: number | null | undefined, format: Format): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  switch (format) {
    case 'pct':
      return `${(value * 100).toFixed(value === 1 || value === 0 ? 0 : 1)}%`;
    case 'score':
      return value.toFixed(3);
    case 'ms':
      return value >= 10000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value).toLocaleString()} ms`;
    case 'int':
      return Math.round(value).toLocaleString();
    case 'usd':
      return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
  }
}

export type Delta = { text: string; tone: 'better' | 'worse' | 'same' };

export function delta(current: number | null | undefined, previous: number | null | undefined, metric: Metric): Delta | null {
  if (current == null || previous == null) return null;
  const diff = current - previous;
  const epsilon = metric.format === 'pct' || metric.format === 'score' ? 0.0005 : 0;
  if (Math.abs(diff) <= epsilon) return { text: 'no change', tone: 'same' };
  const up = diff > 0;
  const tone = up === (metric.better === 'higher') ? 'better' : 'worse';
  const sign = up ? '+' : '−';
  const size = Math.abs(diff);
  let text: string;
  switch (metric.format) {
    case 'pct':
      text = `${sign}${(size * 100).toFixed(1)} pts`;
      break;
    case 'score':
      text = `${sign}${size.toFixed(3)}`;
      break;
    case 'ms':
      text = `${sign}${Math.round(size).toLocaleString()} ms`;
      break;
    case 'usd':
      text = `${sign}$${size.toFixed(4)}`;
      break;
    default:
      text = `${sign}${Math.round(size).toLocaleString()}`;
  }
  return { text, tone };
}

export function paramsLabel(run: Pick<EvalRun, 'suite' | 'params'>): string[] {
  const p = run.params;
  if (run.suite === 'rag') {
    const parts = [p.answer === false ? 'Retrieval only' : p.judge === false ? 'With answers' : 'Answers + judge'];
    parts.push(p.limit ? `First ${p.limit} questions` : 'All questions');
    return parts;
  }
  if (run.suite === 'agent_tools') return [`n = ${p.n ?? 5}`, `k = ${p.k ?? 5}`];
  return ['All cases'];
}

export function sameParams(a: EvalRun, b: EvalRun): boolean {
  const norm = (p: Record<string, unknown>) =>
    JSON.stringify(Object.keys(p).sort().map((key) => [key, p[key] ?? null]));
  return norm(a.params) === norm(b.params);
}

export function elapsed(run: EvalRun, now: number): string {
  const start = new Date(run.started_at).getTime();
  const end = run.finished_at ? new Date(run.finished_at).getTime() : now;
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`;
}

export function when(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const time = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (sameDay) return `Today, ${time}`;
  return `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })}, ${time}`;
}
