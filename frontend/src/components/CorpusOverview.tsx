import type { InsightPayload } from "../lib/api";

type Props = {
  insights: InsightPayload;
};

export function CorpusOverview({ insights }: Props) {
  const summary = insights.summary || insights.analysis;
  const documents = insights.documents || [];
  const stats = insights.stats || {};
  const entities = insights.spotlight_entities || [];
  const relationships = insights.spotlight_relationships || [];

  return (
    <section className="space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ember">Corpus overview</p>
        <h2 className="mt-2 font-display text-3xl text-moss">What we learned from your documents</h2>
        <p className="mt-3 max-w-3xl text-base leading-relaxed text-ink/75">{summary}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Documents", stats.documents ?? documents.length],
          ["Entities", stats.entities ?? 0],
          ["Relationships", stats.relationships ?? 0],
          ["Chunks", stats.chunks ?? 0],
        ].map(([label, value]) => (
          <div key={label as string} className="border border-moss/15 bg-white/70 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-ink/45">{label}</p>
            <p className="mt-1 font-display text-3xl text-moss">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="border border-moss/15 bg-white/65 p-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-moss">Documents analyzed</h3>
          <ul className="mt-3 space-y-3">
            {documents.map((d) => (
              <li key={d.id || d.filename} className="border-b border-moss/10 pb-3 last:border-0 last:pb-0">
                <p className="font-medium text-ink">{d.filename}</p>
                <p className="mt-1 text-sm text-ink/55">
                  Type: <span className="text-ink/80">{d.document_type || "—"}</span>
                  {" · "}
                  Chunking: <span className="text-ink/80">{d.chunking_strategy || "—"}</span>
                  {" · "}
                  {d.chunks ?? 0} chunks
                </p>
              </li>
            ))}
            {!documents.length && <li className="text-sm text-ink/45">No documents yet.</li>}
          </ul>
        </div>

        <div className="border border-moss/15 bg-white/65 p-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-moss">Notable entities</h3>
          <ul className="mt-3 space-y-2">
            {entities.slice(0, 8).map((e) => (
              <li key={`${e.name}-${e.type}`} className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-ink">{e.name}</span>
                <span className="shrink-0 bg-moss/10 px-2 py-0.5 text-xs text-moss">
                  {e.type}
                  {e.degree != null ? ` · ${e.degree}` : ""}
                </span>
              </li>
            ))}
            {!entities.length && <li className="text-sm text-ink/45">No entities extracted yet.</li>}
          </ul>
        </div>
      </div>

      <div className="border border-moss/15 bg-white/65 p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-moss">Example relationships</h3>
        <ul className="mt-3 space-y-2 text-sm">
          {relationships.slice(0, 6).map((r, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className="font-medium text-ink">{r.source}</span>
              <span className="text-xs uppercase tracking-wide text-ember">{r.type}</span>
              <span className="font-medium text-ink">{r.target}</span>
            </li>
          ))}
          {!relationships.length && <li className="text-ink/45">No relationships extracted yet.</li>}
        </ul>
      </div>
    </section>
  );
}
