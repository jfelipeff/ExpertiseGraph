import { useState } from "react";

type Props = {
  onAsk: (question: string) => Promise<any>;
};

export function ExpertPanel({ onAsk }: Props) {
  const [question, setQuestion] = useState(
    "Who should I talk to about AI strategy for telecom companies?"
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  async function submit() {
    setLoading(true);
    try {
      setResult(await onAsk(question));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="animate-rise space-y-4">
      <div>
        <h2 className="font-display text-3xl text-moss">Expert discovery</h2>
        <p className="mt-2 text-ink/65">
          Traverse Consultant → Projects → Clients → Topics and return ranked experts with reasoning.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          className="flex-1 border border-moss/20 bg-white/80 px-3 py-2 outline-none ring-fern/30 focus:ring-2"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button onClick={submit} disabled={loading} className="bg-moss px-4 py-2 font-semibold text-sand">
          {loading ? "Traversing…" : "Find experts"}
        </button>
      </div>
      {result?.narrative && (
        <div className="border border-moss/15 bg-white/70 p-4 text-sm text-ink/80">{result.narrative}</div>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {(result?.experts || []).map((e: any) => (
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
    </section>
  );
}
