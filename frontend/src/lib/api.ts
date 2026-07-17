const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export type FirmForm = {
  name: string;
  description: string;
  industry: string;
  notes: string;
};

export type Job = {
  id: string;
  status: string;
  stage: string;
  progress: number;
  file_stages: Record<string, { stage: string; detail: string }>;
  decisions: Record<string, unknown>;
  stats: Record<string, number>;
  error?: string | null;
};

export async function ingest(firm: FirmForm, files: File[]) {
  const form = new FormData();
  form.append("name", firm.name);
  form.append("description", firm.description);
  form.append("industry", firm.industry);
  form.append("notes", firm.notes);
  files.forEach((f) => form.append("files", f));
  return handle<Job>(await fetch(`${API_BASE}/ingest`, { method: "POST", body: form }));
}

export async function getJob(id: string) {
  return handle<Job>(await fetch(`${API_BASE}/jobs/${id}`));
}

export async function getGraph() {
  return handle<{ nodes: any[]; edges: any[] }>(await fetch(`${API_BASE}/graph`));
}

export async function searchGraph(q: string) {
  return handle<{ results: any[] }>(await fetch(`${API_BASE}/graph/search?q=${encodeURIComponent(q)}`));
}

export async function getNode(id: string) {
  return handle<any>(await fetch(`${API_BASE}/graph/nodes/${encodeURIComponent(id)}`));
}

export async function chat(question: string) {
  return handle<any>(
    await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    })
  );
}

export async function experts(question: string) {
  return handle<any>(
    await fetch(`${API_BASE}/experts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    })
  );
}

export async function gaps() {
  return handle<any>(await fetch(`${API_BASE}/gaps`));
}

export async function temporal() {
  return handle<any>(await fetch(`${API_BASE}/temporal`));
}

export async function documents() {
  return handle<{ documents: any[] }>(await fetch(`${API_BASE}/documents`));
}

export type DemoInfo = {
  mode: string;
  firm: FirmForm & { id?: string };
  documents: Array<{
    filename: string;
    title: string;
    blurb: string;
    year?: number;
    size_mb: number;
  }>;
  description: string;
  graph_ready?: boolean;
  quality?: "llm" | "heuristic" | "partial" | "empty" | string;
  entities?: number;
  relationships?: number;
  llm_relationships?: number;
  seeding?: boolean;
  seed_error?: string | null;
};

export async function getDemoInfo() {
  return handle<DemoInfo>(await fetch(`${API_BASE}/demo`));
}

/** Open shared example. reset=true wipes Neo4j and re-runs LLM (expensive). */
export async function startDemo(reset = false) {
  return handle<Job>(
    await fetch(`${API_BASE}/demo/start?reset=${reset ? "true" : "false"}`, {
      method: "POST",
    })
  );
}

export type InsightPayload = {
  summary?: string;
  analysis: string;
  documents: any[];
  stats: Record<string, number>;
  spotlight_entities: any[];
  spotlight_relationships: any[];
  suggested_questions: Array<{ id: string; question: string; why?: string }>;
  expert_prompts: Array<{ id: string; question: string; why?: string }>;
  llm_provider?: string;
};

export async function getInsights() {
  return handle<InsightPayload>(await fetch(`${API_BASE}/insights`));
}
