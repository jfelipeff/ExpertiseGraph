import { useEffect, useState } from "react";

type Props = {
  loadGaps: () => Promise<any>;
  loadTemporal: () => Promise<any>;
};

export function GapsPanel({ loadGaps, loadTemporal }: Props) {
  const [gaps, setGaps] = useState<any>(null);
  const [temporal, setTemporal] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [g, t] = await Promise.all([loadGaps(), loadTemporal()]);
        setGaps(g);
        setTemporal(t);
      } finally {
        setLoading(false);
      }
    })();
  }, [loadGaps, loadTemporal]);

  if (loading) {
    return <p className="animate-rise text-ink/60">Scanning sparse regions…</p>;
  }

  return (
    <section className="animate-rise space-y-8">
      <div>
        <h2 className="font-display text-3xl text-moss">What do we not know?</h2>
        <p className="mt-2 text-ink/65">{gaps?.summary}</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {(gaps?.gaps || []).map((g: any) => (
          <article key={g.entity_id} className="border border-moss/15 bg-white/65 p-4">
            <h3 className="font-display text-xl text-moss">{g.entity}</h3>
            <p className="text-xs uppercase text-ink/50">
              {g.type} · degree {g.degree} · sparsity {g.sparsity_score}
            </p>
            <p className="mt-2 text-sm">
              <span className="font-semibold">Known:</span> {(g.known || []).join(", ") || "—"}
            </p>
            <p className="mt-1 text-sm">
              <span className="font-semibold">Missing:</span> {(g.missing || []).join(", ") || "—"}
            </p>
            <p className="mt-2 text-xs italic text-ink/55">{g.question}</p>
          </article>
        ))}
      </div>

      <div>
        <h3 className="font-display text-2xl text-moss">Temporal knowledge</h3>
        <p className="mt-1 text-sm text-ink/60">Recently added relationships and documents.</p>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div className="border border-moss/15 bg-white/60 p-4">
            <h4 className="font-semibold text-moss">New relationships</h4>
            <ul className="mt-2 space-y-2 text-sm">
              {(temporal?.relationships || []).map((r: any, i: number) => (
                <li key={i} className="border-b border-moss/10 pb-2">
                  {r.source} —{r.type}→ {r.target}
                  <div className="text-xs text-ink/50">
                    {r.source_document} · {r.created_at}
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div className="border border-moss/15 bg-white/60 p-4">
            <h4 className="font-semibold text-moss">Documents</h4>
            <ul className="mt-2 space-y-2 text-sm">
              {(temporal?.documents || []).map((d: any, i: number) => (
                <li key={i}>
                  {d.filename} · {d.document_type}
                  <div className="text-xs text-ink/50">{d.created_at}</div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
