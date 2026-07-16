import { useState } from "react";
import ReactMarkdown from "react-markdown";

type Props = {
  onAsk: (question: string) => Promise<any>;
};

const SUGGESTIONS = [
  "What expertise do we have in telecom?",
  "Which methodologies have been used across multiple projects?",
  "Which projects mention generative AI?",
  "What consultants appear most frequently in AI-related work?",
  "What changed in the knowledge base this month?",
];

export function ChatPanel({ onAsk }: Props) {
  const [question, setQuestion] = useState(SUGGESTIONS[0]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(q?: string) {
    const ask = (q ?? question).trim();
    if (!ask) return;
    setQuestion(ask);
    setLoading(true);
    setError(null);
    try {
      setResult(await onAsk(ask));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="animate-rise grid gap-6 lg:grid-cols-[1fr_1fr]">
      <div>
        <h2 className="font-display text-3xl text-moss">Hybrid GraphRAG chat</h2>
        <p className="mt-2 text-ink/65">
          Vector retrieval + graph retrieval → context fusion → grounded answer with citations.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => submit(s)}
              className="bg-white/70 px-3 py-1.5 text-left text-xs text-moss hover:bg-white"
            >
              {s}
            </button>
          ))}
        </div>
        <textarea
          className="mt-4 min-h-28 w-full border border-moss/20 bg-white/80 px-3 py-2 outline-none ring-fern/30 focus:ring-2"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button
          onClick={() => submit()}
          disabled={loading}
          className="mt-3 bg-ember px-4 py-2 font-semibold text-sand disabled:opacity-50"
        >
          {loading ? "Retrieving…" : "Ask with evidence"}
        </button>
        {error && <p className="mt-3 text-sm text-ember">{error}</p>}
      </div>
      <div className="border border-moss/15 bg-white/70 p-4">
        {!result && <p className="text-sm text-ink/55">Answers never invent facts without retrieved evidence.</p>}
        {result && (
          <div className="space-y-4 text-sm">
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
            <div>
              <h4 className="font-semibold text-moss">Citations</h4>
              <ul className="mt-2 space-y-2">
                {(result.citations || []).map((c: any, i: number) => (
                  <li key={i} className="border-l-2 border-fern/40 pl-3 text-ink/70">
                    {c.document} p.{c.page_number} — {c.snippet}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-moss">Graph entities</h4>
              <p className="mt-1 text-ink/70">
                {(result.entities || []).map((e: any) => e.name).join(", ") || "—"}
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-moss">Relationships</h4>
              <ul className="mt-2 space-y-1 text-ink/70">
                {(result.relationships || []).slice(0, 8).map((r: any, i: number) => (
                  <li key={i}>
                    {r.from} —{r.type}→ {r.to}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
