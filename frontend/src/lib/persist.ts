const STORAGE_KEY = "expertisegraph-ui";

export type PersistedState = {
  mode: "choose" | "demo" | "custom";
  firm?: {
    name: string;
    description: string;
    industry: string;
    notes: string;
  };
  jobId?: string | null;
  sidebar?: string;
  showGraph?: boolean;
  hasWorkspace?: boolean;
};

export function loadPersisted(): PersistedState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedState;
  } catch {
    return null;
  }
}

export function savePersisted(state: PersistedState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore quota / private mode
  }
}

export function clearPersisted() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
