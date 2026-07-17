import { useEffect, useMemo, useState } from "react";
import {
  DemoInfo,
  FirmForm,
  InsightPayload,
  Job,
  chat,
  documents,
  experts,
  gaps,
  getDemoInfo,
  getGraph,
  getInsights,
  getJob,
  getNode,
  ingest,
  searchGraph,
  startDemo,
  temporal,
} from "./lib/api";
import { clearPersisted, loadPersisted, savePersisted } from "./lib/persist";
import { GraphExplorer } from "./components/GraphExplorer";
import { AskWorkspace } from "./components/AskWorkspace";
import { CorpusOverview } from "./components/CorpusOverview";
import { ExpertWorkspace } from "./components/ExpertWorkspace";
import { GapsPanel } from "./components/GapsPanel";

type Mode = "choose" | "demo" | "custom";
type SidebarView = "overview" | "ask" | "experts" | "gaps" | "selection";

const emptyFirm: FirmForm = {
  name: "Acme Consulting",
  description: "Management consulting firm specializing in telecom and digital transformation.",
  industry: "Management Consulting",
  notes: "",
};

const TAGLINE = "LLM + AI + GraphRAG to turn institutional knowledge into searchable expertise.";

export default function App() {
  const [mode, setMode] = useState<Mode>("choose");
  const [firm, setFirm] = useState<FirmForm>(emptyFirm);
  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showGraph, setShowGraph] = useState(true);
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [selected, setSelected] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [demoInfo, setDemoInfo] = useState<DemoInfo | null>(null);
  const [insights, setInsights] = useState<InsightPayload | null>(null);
  const [sidebar, setSidebar] = useState<SidebarView>("overview");
  const [hydrated, setHydrated] = useState(false);

  const ingestDone = useMemo(
    () =>
      !!(
        insights ||
        (job && (job.status === "completed" || job.status === "completed_with_errors")) ||
        docs.length > 0
      ),
    [job, insights, docs]
  );
  const ingesting = !!(job && job.status !== "failed" && job.status !== "completed" && job.status !== "completed_with_errors");

  // Restore UI + Neo4j corpus on reload
  useEffect(() => {
    (async () => {
      const saved = loadPersisted();
      try {
        const [docPayload, insightPayload, graphPayload, demo] = await Promise.all([
          documents().catch(() => ({ documents: [] })),
          getInsights().catch(() => null),
          getGraph().catch(() => ({ nodes: [], edges: [] })),
          getDemoInfo().catch(() => null),
        ]);
        if (demo) setDemoInfo(demo);

        const hasData =
          demo?.graph_ready ||
          (docPayload.documents?.length || 0) > 0 ||
          (graphPayload.nodes?.length || 0) > 0;

        // Prefer the shared pre-built example (seeded on API deploy)
        if (demo?.graph_ready || demo?.seeding) {
          setMode("demo");
          if (demo.firm) {
            setFirm({
              name: demo.firm.name,
              description: demo.firm.description,
              industry: demo.firm.industry,
              notes: demo.firm.notes || "",
            });
          }
        } else if (saved?.mode && saved.mode !== "choose") {
          setMode(saved.mode);
        } else if (hasData) {
          setMode(saved?.mode === "custom" ? "custom" : "demo");
        }

        if (saved?.firm && !demo?.graph_ready) setFirm(saved.firm);
        if (saved?.sidebar) setSidebar(saved.sidebar as SidebarView);
        if (typeof saved?.showGraph === "boolean") setShowGraph(saved.showGraph);

        if (hasData) {
          setDocs(docPayload.documents || []);
          if (insightPayload) setInsights(insightPayload);
          setGraphData(graphPayload);
          if (demo?.graph_ready) {
            setJob({
              id: "demo-cached",
              status: "completed",
              stage: "cached",
              progress: 100,
              file_stages: {},
              decisions: {},
              stats: {},
            });
          }
        }

        if (saved?.jobId && saved.jobId !== "demo-cached") {
          try {
            const existing = await getJob(saved.jobId);
            setJob(existing);
          } catch {
            // stale job id
          }
        }
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  // While the API is seeding the shared example on deploy, poll until ready
  useEffect(() => {
    if (!hydrated || !demoInfo?.seeding || demoInfo.graph_ready) return;
    const t = setInterval(async () => {
      try {
        const demo = await getDemoInfo();
        setDemoInfo(demo);
        if (demo.graph_ready) {
          const [docPayload, insightPayload, graphPayload] = await Promise.all([
            documents(),
            getInsights(),
            getGraph(),
          ]);
          setDocs(docPayload.documents || []);
          setInsights(insightPayload);
          setGraphData(graphPayload);
          setJob({
            id: "demo-cached",
            status: "completed",
            stage: "cached",
            progress: 100,
            file_stages: {},
            decisions: {},
            stats: {},
          });
          setMode("demo");
          setSidebar("overview");
        }
      } catch {
        // ignore transient errors while Render wakes / seed runs
      }
    }, 2500);
    return () => clearInterval(t);
  }, [hydrated, demoInfo?.seeding, demoInfo?.graph_ready]);

  useEffect(() => {
    if (!hydrated || mode === "choose") return;
    savePersisted({
      mode,
      firm,
      jobId: job?.id || null,
      sidebar,
      showGraph,
      hasWorkspace: ingestDone,
    });
  }, [hydrated, mode, firm, job?.id, sidebar, showGraph, ingestDone]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "completed_with_errors" || job.status === "failed") {
      return;
    }
    const t = setInterval(async () => {
      try {
        setJob(await getJob(job.id));
      } catch (e: any) {
        setError(e.message);
      }
    }, 1500);
    return () => clearInterval(t);
  }, [job]);

  useEffect(() => {
    if (!job) return;
    if (job.status !== "completed" && job.status !== "completed_with_errors") return;
    (async () => {
      try {
        await refreshGraph();
        const [docPayload, insightPayload] = await Promise.all([documents(), getInsights()]);
        setDocs(docPayload.documents);
        setInsights(insightPayload);
        setSidebar("overview");
      } catch (e: any) {
        setError(e.message);
      }
    })();
  }, [job?.status, job?.id]);

  async function refreshGraph() {
    setGraphData(await getGraph());
  }

  async function onIngest() {
    setError(null);
    if (!firm.name.trim()) {
      setError("Company name is required.");
      return;
    }
    if (!files.length) {
      setError("Upload at least one PDF, DOCX, or TXT file.");
      return;
    }
    setBusy(true);
    try {
      setInsights(null);
      setJob(await ingest(firm, files));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onOpenDemo() {
    setError(null);
    setBusy(true);
    setMode("demo");
    try {
      const info = demoInfo || (await getDemoInfo());
      setDemoInfo(info);
      if (info.firm) {
        setFirm({
          name: info.firm.name,
          description: info.firm.description,
          industry: info.firm.industry,
          notes: info.firm.notes || "",
        });
      }

      // Prefer cached graph (no tokens). Only ingest if Neo4j does not have the example yet.
      const created = await startDemo(false);
      setJob(created);

      if (created.status === "completed" || created.stage === "cached") {
        const [docPayload, insightPayload, graphPayload] = await Promise.all([
          documents(),
          getInsights(),
          getGraph(),
        ]);
        setDocs(docPayload.documents);
        setInsights(insightPayload);
        setGraphData(graphPayload);
        setSidebar("overview");
      }
    } catch (e: any) {
      setError(e.message);
      setMode("choose");
    } finally {
      setBusy(false);
    }
  }

  async function onRebuildDemo() {
    const ok = window.confirm(
      "Rebuild the shared example graph? This clears Neo4j data and re-runs the LLM (uses tokens for everyone)."
    );
    if (!ok) return;
    setError(null);
    setBusy(true);
    setMode("demo");
    setInsights(null);
    setDocs([]);
    try {
      const created = await startDemo(true);
      setJob(created);
      if (demoInfo?.firm) {
        setFirm({
          name: demoInfo.firm.name,
          description: demoInfo.firm.description,
          industry: demoInfo.firm.industry,
          notes: demoInfo.firm.notes || "",
        });
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onSelectNode(id: string) {
    try {
      const detail = await getNode(id);
      setSelected({ kind: "node", ...detail });
      setSidebar("selection");
    } catch {
      const node = graphData.nodes.find((n) => n.id === id);
      setSelected({ kind: "node", node, relationships: [] });
      setSidebar("selection");
    }
  }

  function onSelectEdge(edge: any) {
    setSelected({ kind: "edge", ...edge });
    setSidebar("selection");
  }

  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-mesh text-ink/60">
        Loading ExpertiseGraph…
      </div>
    );
  }

  if (mode === "choose") {
    return (
      <div className="min-h-screen bg-mesh text-ink">
        <main className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16">
          <div className="animate-rise">
            <p className="font-display text-5xl font-bold tracking-tight text-moss md:text-6xl">
              ExpertiseGraph
            </p>
            <p className="mt-4 max-w-2xl text-lg text-ink/70">{TAGLINE}</p>
          </div>

          <div className="animate-rise-delay mt-12 grid gap-6 md:grid-cols-2">
            <button
              onClick={onOpenDemo}
              disabled={busy}
              className="group border border-moss/20 bg-white/70 p-8 text-left transition hover:border-fern hover:bg-white disabled:opacity-60"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ember">Example mode</p>
              <h2 className="mt-3 font-display text-3xl text-moss">See how a graph looks</h2>
              <p className="mt-3 text-sm leading-relaxed text-ink/65">
                {demoInfo?.graph_ready
                  ? "Open the shared StratCore example — already loaded on the server for every visitor."
                  : demoInfo?.seeding
                    ? "The server is seeding the shared example after deploy. You can wait here or refresh shortly."
                    : demoInfo?.description ||
                      "Load sample research and explore a dense example graph."}
              </p>
              <ul className="mt-5 space-y-2 text-sm text-ink/70">
                {(demoInfo?.documents || []).map((d) => (
                  <li key={d.filename}>
                    <span className="font-semibold text-moss">{d.title}</span>
                    <span className="text-ink/50"> — {d.blurb}</span>
                  </li>
                ))}
              </ul>
              <span className="mt-8 inline-block bg-ember px-4 py-2 text-sm font-semibold text-sand">
                {busy
                  ? demoInfo?.graph_ready
                    ? "Opening…"
                    : "Building example…"
                  : demoInfo?.graph_ready
                    ? "Explore example graph"
                    : "Build example graph"}
              </span>
            </button>

            <button
              onClick={() => setMode("custom")}
              className="group border border-moss/20 bg-white/50 p-8 text-left transition hover:border-moss hover:bg-white/80"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-moss">Your firm</p>
              <h2 className="mt-3 font-display text-3xl text-moss">Upload your knowledge</h2>
              <p className="mt-3 text-sm leading-relaxed text-ink/65">
                Enter company details, upload PDF / DOCX / TXT files, and build an institutional
                memory graph from your own documents.
              </p>
              <span className="mt-8 inline-block bg-moss px-4 py-2 text-sm font-semibold text-sand">
                Start with my files
              </span>
            </button>
          </div>
          {error && (
            <div className="mt-6 border border-ember/40 bg-ember/10 px-4 py-3 text-sm text-ember">{error}</div>
          )}
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-mesh text-ink">
      <header className="border-b border-moss/15 bg-sand/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1400px] items-end justify-between gap-4 px-4 py-5 md:px-6">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <p className="font-display text-3xl font-bold tracking-tight text-moss md:text-4xl">
                ExpertiseGraph
              </p>
              <span
                className={`px-2 py-1 text-xs font-semibold uppercase tracking-wide ${
                  mode === "demo" ? "bg-ember/15 text-ember" : "bg-moss/10 text-moss"
                }`}
              >
                {mode === "demo" ? "Example mode" : "Your firm"}
              </span>
            </div>
            <p className="mt-2 max-w-2xl text-sm text-ink/65 md:text-base">{TAGLINE}</p>
          </div>
          <button
            onClick={() => {
              clearPersisted();
              setMode("choose");
              setJob(null);
              setInsights(null);
              setDocs([]);
              setError(null);
            }}
            className="bg-white/60 px-3 py-2 text-sm font-semibold text-ink/70 hover:bg-white"
          >
            Switch mode
          </button>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col lg:flex-row">
        <aside className="w-full shrink-0 border-b border-moss/15 bg-sand/50 lg:w-64 lg:border-b-0 lg:border-r">
          <div className="sticky top-0 p-4">
            <p className="px-2 pb-3 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
              Navigate
            </p>
            <nav className="space-y-1">
              {(
                [
                  ["overview", "Overview"],
                  ["ask", "Ask"],
                  ["experts", "Experts"],
                  ["gaps", "Knowledge gaps"],
                  ["selection", "Selection"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setSidebar(id)}
                  disabled={!ingestDone && id !== "overview"}
                  className={`block w-full px-3 py-2.5 text-left text-sm font-semibold transition disabled:opacity-35 ${
                    sidebar === id ? "bg-moss text-sand" : "text-moss hover:bg-white/70"
                  }`}
                >
                  {label}
                </button>
              ))}
            </nav>

            <div className="mt-8 px-2">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">Status</p>
              {job && (
                <div className="mt-3">
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="truncate pr-2">{job.stage}</span>
                    <span>{job.progress}%</span>
                  </div>
                  <div className="h-1.5 bg-mist">
                    <div className="h-1.5 bg-fern transition-all" style={{ width: `${job.progress}%` }} />
                  </div>
                </div>
              )}
              {!!docs.length && (
                <ul className="mt-3 space-y-2 text-xs text-ink/65">
                  {docs.map((d) => (
                    <li key={d.id}>
                      <span className="font-medium text-ink/80">{d.filename}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex-1 px-4 py-6 md:px-8">
            {error && (
              <div className="mb-4 border border-ember/40 bg-ember/10 px-4 py-3 text-sm text-ember">
                {error}
              </div>
            )}

            {!ingestDone && (
              <section className="animate-rise grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
                <div>
                  {mode === "demo" ? (
                    <>
                      <h2 className="font-display text-3xl text-moss">Example corpus</h2>
                      <p className="mt-2 text-ink/65">
                        {demoInfo?.seeding
                          ? "The shared example is being built once on the server (deploy seed). This page will open automatically when it’s ready — visitors after you won’t pay this cost."
                          : "Building a knowledge graph from StratCore consulting project reports (Atlas & Orion)."}
                      </p>
                      <div className="mt-6 space-y-4">
                        {(demoInfo?.documents || []).map((d) => (
                          <article key={d.filename} className="border border-moss/15 bg-white/65 p-4">
                            <h3 className="font-display text-xl text-moss">{d.title}</h3>
                            <p className="mt-1 text-sm text-ink/65">{d.blurb}</p>
                          </article>
                        ))}
                      </div>
                      {demoInfo?.seed_error && (
                        <p className="mt-4 text-sm text-ember">{demoInfo.seed_error}</p>
                      )}
                      {!ingesting && !demoInfo?.seeding && (
                        <button
                          onClick={onOpenDemo}
                          disabled={busy}
                          className="mt-6 bg-ember px-5 py-3 font-semibold text-sand disabled:opacity-50"
                        >
                          {busy ? "Starting…" : demoInfo?.graph_ready ? "Open example graph" : "Build example graph"}
                        </button>
                      )}
                      {demoInfo?.seeding && (
                        <p className="mt-6 text-sm font-semibold text-moss">Seeding shared example…</p>
                      )}
                    </>
                  ) : (
                    <>
                      <h2 className="font-display text-3xl text-moss">Company information</h2>
                      <div className="mt-6 space-y-4">
                        {(
                          [
                            ["name", "Company name"],
                            ["industry", "Industry"],
                          ] as const
                        ).map(([key, label]) => (
                          <label key={key} className="block">
                            <span className="text-sm font-semibold text-moss">{label}</span>
                            <input
                              className="mt-1 w-full border border-moss/20 bg-white/70 px-3 py-2 outline-none focus:ring-2 focus:ring-fern/30"
                              value={firm[key]}
                              onChange={(e) => setFirm({ ...firm, [key]: e.target.value })}
                            />
                          </label>
                        ))}
                        <label className="block">
                          <span className="text-sm font-semibold text-moss">Company description</span>
                          <textarea
                            className="mt-1 min-h-24 w-full border border-moss/20 bg-white/70 px-3 py-2 outline-none focus:ring-2 focus:ring-fern/30"
                            value={firm.description}
                            onChange={(e) => setFirm({ ...firm, description: e.target.value })}
                          />
                        </label>
                      </div>
                      <div className="mt-8">
                        <h3 className="font-display text-2xl text-moss">File upload</h3>
                        <label className="mt-4 flex cursor-pointer flex-col items-center justify-center border border-dashed border-moss/35 bg-white/50 px-6 py-10 hover:border-fern">
                          <span className="font-semibold text-moss">Drop files or click to browse</span>
                          <span className="mt-1 text-sm text-ink/55">
                            {files.length ? `${files.length} file(s) selected` : "PDF, DOCX, TXT"}
                          </span>
                          <input
                            type="file"
                            multiple
                            accept=".pdf,.docx,.txt"
                            className="hidden"
                            onChange={(e) => setFiles(Array.from(e.target.files || []))}
                          />
                        </label>
                        <button
                          onClick={onIngest}
                          disabled={busy || ingesting}
                          className="mt-6 bg-ember px-5 py-3 font-semibold text-sand disabled:opacity-50"
                        >
                          {busy || ingesting ? "Working…" : "Ingest & build knowledge graph"}
                        </button>
                      </div>
                    </>
                  )}
                </div>
                <aside className="border border-moss/15 bg-white/55 p-5">
                  <h3 className="font-display text-xl text-moss">Ingestion progress</h3>
                  {!job && (
                    <p className="mt-3 text-sm text-ink/60">Parse → classify → chunk → embed → extract → index</p>
                  )}
                  {job && (
                    <div className="mt-4 space-y-3">
                      {Object.entries(job.file_stages || {}).map(([name, st]) => (
                        <div key={name} className="border-l-2 border-fern/50 pl-3 text-sm">
                          <div className="font-semibold">{name}</div>
                          <div className="text-ink/60">
                            {st.stage}
                            {st.detail ? ` — ${st.detail}` : ""}
                          </div>
                        </div>
                      ))}
                      {job.error && <p className="text-sm text-ember">{job.error}</p>}
                    </div>
                  )}
                </aside>
              </section>
            )}

            {ingestDone && insights && sidebar === "overview" && (
              <div className="animate-rise space-y-8">
                <CorpusOverview insights={insights} />
                {showGraph && (
                  <section>
                    <h2 className="font-display text-3xl text-moss">Knowledge graph</h2>
                    <p className="mt-1 text-ink/60">Explore entities and provenance-backed relationships.</p>
                    <div className="mt-4">
                      <GraphExplorer
                        data={graphData}
                        onSelectNode={onSelectNode}
                        onSelectEdge={onSelectEdge}
                        onSearch={async (q) => (await searchGraph(q)).results}
                      />
                    </div>
                  </section>
                )}
              </div>
            )}

            {ingestDone && insights && sidebar === "ask" && (
              <div className="animate-rise">
                <AskWorkspace insights={insights} onAsk={chat} />
              </div>
            )}

            {ingestDone && insights && sidebar === "experts" && (
              <div className="animate-rise">
                <ExpertWorkspace prompts={insights.expert_prompts} onAsk={experts} />
              </div>
            )}

            {ingestDone && sidebar === "gaps" && (
              <div className="animate-rise">
                <GapsPanel loadGaps={gaps} loadTemporal={temporal} />
              </div>
            )}

            {sidebar === "selection" && (
              <div className="animate-rise border border-moss/15 bg-white/70 p-5 text-sm">
                {!selected && <p className="text-ink/50">Click a node or edge in the graph (Overview).</p>}
                {selected?.kind === "edge" && (
                  <>
                    <h2 className="font-display text-2xl text-moss">Relationship</h2>
                    <p className="mt-2 font-semibold">{selected.type}</p>
                    <p className="mt-3 text-ink/75">{selected.evidence || "No evidence."}</p>
                    <p className="mt-2 text-ink/45">
                      {selected.source_document} · p.{selected.page_number ?? "—"} · conf{" "}
                      {selected.confidence ?? "—"}
                    </p>
                  </>
                )}
                {selected?.kind === "node" && (
                  <>
                    <h2 className="font-display text-2xl text-moss">
                      {selected.node?.name || selected.node?.label || "Node"}
                    </h2>
                    <p className="text-ink/55">{selected.node?.entity_type || selected.node?.type}</p>
                    <pre className="mt-4 max-h-96 overflow-auto bg-ink/5 p-3 text-xs">
                      {JSON.stringify(selected, null, 2)}
                    </pre>
                  </>
                )}
              </div>
            )}

            {ingestDone && !insights && (
              <p className="text-ink/60">Preparing insights from the knowledge graph…</p>
            )}
          </div>

          {/* Bottom graph controls */}
          {ingestDone && (
            <div className="sticky bottom-0 border-t border-moss/15 bg-sand/90 px-4 py-3 backdrop-blur md:px-8">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setShowGraph((v) => !v)}
                  className="bg-white/80 px-3 py-2 text-sm font-semibold text-moss hover:bg-white"
                >
                  {showGraph ? "Hide graph" : "Show graph"}
                </button>
                <button
                  onClick={refreshGraph}
                  className="bg-white/80 px-3 py-2 text-sm font-semibold text-moss hover:bg-white"
                >
                  Refresh graph
                </button>
                {mode === "demo" && (
                  <button
                    onClick={onRebuildDemo}
                    disabled={busy || ingesting}
                    className="bg-ember/15 px-3 py-2 text-sm font-semibold text-ember hover:bg-ember/25 disabled:opacity-40"
                  >
                    Rebuild example
                  </button>
                )}
                <span className="ml-auto text-xs text-ink/45">
                  {graphData.nodes.length} nodes · {graphData.edges.length} edges
                </span>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
