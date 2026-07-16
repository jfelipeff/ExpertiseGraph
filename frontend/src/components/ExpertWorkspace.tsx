import { useState } from "react";

type Question = { id: string; question: string; why?: string };

type Props = {
  prompts: Question[];
  onAsk: (question: string) => Promise<any>;
};

export function ExpertWorkspace({ prompts, onAsk }: Props) {
  const [custom, setCustom] = useState("");
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function find(question: string) {
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
    <section className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">Expert discovery</p>
        <h2 className="mt-2 font-display text-3xl text-moss">Who should you talk to?</h2>
        <p className="mt-2 max-w-3xl text-ink/65">
          Traverse people and entities through projects, clients, and topics — then rank who is most
          connected to the question.
        </p>
      </div>

      <div className="space-y-3">
        {prompts.map((p) => (
          <div
            key={p.id}
            className="flex flex-col gap-3 border border-moss/15 bg-white/65 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{p.question}</p>
              {p.why && <p className="mt-1 text-xs text-ink/50">{p.why}</p>}
            </div>
            <button
              onClick={() => find(p.question)}
              disabled={loading}
              className="shrink-0 bg-moss px-4 py-2 text-sm font-semibold text-sand disabled:opacity-50"
            >
              {loading && activeQuestion === p.question ? "Finding…" : "Find experts"}
            </button>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && find(custom)}
          placeholder="Ask who to talk to about another topic…"
          className="w-full border border-moss/15 bg-white/50 px-4 py-3 text-ink outline-none ring-fern/30 placeholder:text-ink/35 focus:bg-white/80 focus:ring-2"
        />
        <button
          onClick={() => find(custom)}
          disabled={loading || !custom.trim()}
          className="bg-moss px-4 py-3 text-sm font-semibold text-sand disabled:opacity-40"
        >
          Find
        </button>
      </div>
      {error && <p className="text-sm text-ember">{error}</p>}

      {result && (
        <div className="space-y-4">
          {activeQuestion && (
            <p className="text-sm text-ink/60">
              Results for <span className="font-medium text-ink">{activeQuestion}</span>
            </p>
          )}
          {result.narrative && (
            <div className="border border-moss/15 bg-white/70 p-4 text-sm text-ink/80">{result.narrative}</div>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            {(result.experts || []).map((e: any) => (
              <article key={e.id || e.name} className="border border-moss/15 bg-white/65 p-4">
                <h3 className="font-display text-xl text-moss">{e.name}</h3>
                <p className="text-xs uppercase tracking-wide text-ink/50">
                  {e.type} · score {e.score}
                </p>
                <p className="mt-2 text-sm text-ink/75">{e.reasoning}</p>
                {!!e.topics?.length && (
                  <p className="mt-2 text-xs text-ink/55">Topics: {e.topics.filter(Boolean).join(", ")}</p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
