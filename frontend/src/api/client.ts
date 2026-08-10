const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";
const API_KEY = import.meta.env.VITE_API_DEV_KEY ?? "dev-local-key";

export type RunStatus = "running" | "paused" | "completed" | "failed";

export interface RunSummary {
  run_id: string;
  task: string;
  status: RunStatus;
  max_revisions: number;
  created_at: string;
  updated_at: string;
}

export interface CheckpointSummary {
  checkpoint_id: string;
  next: string[];
  step: number | null;
}

export function apiHeaders(json = true): HeadersInit {
  const h: Record<string, string> = { "X-API-Key": API_KEY };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => resp.statusText);
    throw new Error(`API error ${resp.status}: ${text}`);
  }
  return resp.json() as Promise<T>;
}

export async function createRun(task: string, maxRevisions?: number): Promise<RunSummary> {
  const resp = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: apiHeaders(),
    body: JSON.stringify({ task, max_revisions: maxRevisions ?? null }),
  });
  return handle(resp);
}

export async function listRuns(): Promise<RunSummary[]> {
  const resp = await fetch(`${API_BASE}/runs`, { headers: apiHeaders(false) });
  return handle(resp);
}

export async function getRun(runId: string): Promise<RunSummary> {
  const resp = await fetch(`${API_BASE}/runs/${runId}`, { headers: apiHeaders(false) });
  return handle(resp);
}

export async function getHistory(runId: string): Promise<CheckpointSummary[]> {
  const resp = await fetch(`${API_BASE}/runs/${runId}/history`, { headers: apiHeaders(false) });
  return handle(resp);
}

export function streamUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/stream`;
}

export function resumeUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/resume`;
}

export function replayFromUrl(runId: string, checkpointId: string): string {
  return `${API_BASE}/runs/${runId}/replay_from/${checkpointId}`;
}
