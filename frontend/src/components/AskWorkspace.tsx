import { useState } from "react";
import ReactMarkdown from "react-markdown";
import type { InsightPayload } from "../lib/api";

type Question = { id: string; question: string; why?: string };

type Props = {
  insights: InsightPayload;
  onAsk: (question: string) => Promise<any>;
};

export function AskWorkspace({ insights, onAsk }: Props) {
  const [custom, setCustom] = useState("");
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const suggestedQuestions = insights.suggested_questions || [];

  async function answer(question: string) {
    const q = question.trim();
    if (!q) return;
    setActiveQuestion(q);
    setLoading(true);
    setError(null);
    try {
      setResult(await onAsk(q));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ember">Ask</p>
        <h2 className="mt-2 font-display text-3xl text-moss">Questions worth asking</h2>
        <p className="mt-2 max-w-3xl text-ink/65">
          Hybrid GraphRAG — vector search over chunks, then graph expansion for entities and
          relationships. Answers cite evidence only.
        </p>
      </div>

      <div className="space-y-3">
        {suggestedQuestions.map((q: Question) => (
          <div
            key={q.id}
            className="flex flex-col gap-3 border border-moss/15 bg-white/65 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{q.question}</p>
              {q.why && <p className="mt-1 text-xs text-ink/50">{q.why}</p>}
            </div>
            <button
              onClick={() => answer(q.question)}
              disabled={loading}
              className="shrink-0 bg-ember px-4 py-2 text-sm font-semibold text-sand disabled:opacity-50"
            >
              {loading && activeQuestion === q.question ? "Answering…" : "Answer with GraphRAG"}
            </button>
          </div>
        ))}
      </div>

      <div>
        <label className="block">
          <span className="sr-only">Ask another question</span>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && answer(custom)}
              placeholder="Ask another question about this knowledge base…"
              className="w-full border border-moss/15 bg-white/50 px-4 py-3 text-ink outline-none ring-fern/30 placeholder:text-ink/35 focus:bg-white/80 focus:ring-2"
            />
            <button
              onClick={() => answer(custom)}
              disabled={loading || !custom.trim()}
              className="bg-moss px-4 py-3 text-sm font-semibold text-sand disabled:opacity-40"
            >
              Ask
            </button>
          </div>
        </label>
        {error && <p className="mt-2 text-sm text-ember">{error}</p>}
      </div>

      {(loading || result) && (
        <div className="border border-moss/15 bg-white/75 p-5">
          {activeQuestion && (
            <p className="text-xs font-semibold uppercase tracking-wide text-moss/70">
              {loading ? "Retrieving evidence…" : "Answer"}
            </p>
          )}
          {activeQuestion && <p className="mt-1 font-medium text-ink/80">{activeQuestion}</p>}
          {loading && !result && (
            <p className="mt-4 text-sm text-ink/50">Running hybrid vector + graph retrieval…</p>
          )}
          {result && (
            <div className="mt-4 space-y-4 text-sm">
              <div className="prose prose-sm max-w-none text-ink">
                <ReactMarkdown>{result.answer}</ReactMarkdown>
              </div>
              {!!result.citations?.length && (
                <div>
                  <h4 className="font-semibold text-moss">Citations</h4>
                  <ul className="mt-2 space-y-2">
                    {result.citations.map((c: any, i: number) => (
                      <li key={i} className="border-l-2 border-fern/40 pl-3 text-ink/70">
                        {c.document} p.{c.page_number} — {c.snippet}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {!!result.relationships?.length && (
                <div>
                  <h4 className="font-semibold text-moss">Graph relationships used</h4>
                  <ul className="mt-2 space-y-1 text-ink/70">
                    {result.relationships.slice(0, 8).map((r: any, i: number) => (
                      <li key={i}>
                        {r.from} —{r.type}→ {r.to}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
