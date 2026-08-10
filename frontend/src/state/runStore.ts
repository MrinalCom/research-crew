import { create } from "zustand";
import type { SSEEvent } from "../api/sse";
import type { InterruptPayload, NodeStatusValue } from "../types";

export type RunPhase = "idle" | "streaming" | "paused" | "completed" | "error";

export interface LogEntry {
  id: number;
  node: string;
  kind: "status" | "token" | "system";
  text: string;
  timestamp: number;
}

interface RunState {
  runId: string | null;
  phase: RunPhase;
  nodeStatuses: Partial<Record<string, NodeStatusValue>>;
  log: LogEntry[];
  pendingInterrupt: InterruptPayload | null;
  errorMessage: string | null;

  startRun: (runId: string) => void;
  applyEvent: (evt: SSEEvent) => void;
  appendSystemMessage: (text: string) => void;
}

let nextLogId = 0;

export const useRunStore = create<RunState>((set) => ({
  runId: null,
  phase: "idle",
  nodeStatuses: {},
  log: [],
  pendingInterrupt: null,
  errorMessage: null,

  startRun: (runId) =>
    set({
      runId,
      phase: "streaming",
      nodeStatuses: {},
      log: [],
      pendingInterrupt: null,
      errorMessage: null,
    }),

  appendSystemMessage: (text) =>
    set((s) => ({
      log: [...s.log, { id: nextLogId++, node: "system", kind: "system", text, timestamp: Date.now() }],
    })),

  applyEvent: (evt) => {
    let data: any = {};
    try {
      data = evt.data ? JSON.parse(evt.data) : {};
    } catch {
      data = {};
    }

    switch (evt.event) {
      case "node_status": {
        set((s) => ({
          phase: s.phase === "paused" ? "streaming" : s.phase,
          nodeStatuses: { ...s.nodeStatuses, [data.node]: data.status },
          log: [
            ...s.log,
            { id: nextLogId++, node: data.node, kind: "status", text: `${data.node} ${data.status}`, timestamp: Date.now() },
          ],
        }));
        break;
      }
      case "token": {
        set((s) => {
          const log = [...s.log];
          const last = log[log.length - 1];
          if (last && last.kind === "token" && last.node === data.node) {
            log[log.length - 1] = { ...last, text: last.text + data.content };
          } else {
            log.push({ id: nextLogId++, node: data.node, kind: "token", text: data.content, timestamp: Date.now() });
          }
          return { log };
        });
        break;
      }
      case "interrupt": {
        set({ phase: "paused", pendingInterrupt: data.payload ?? null });
        break;
      }
      case "run_complete": {
        set({ phase: "completed", pendingInterrupt: null });
        break;
      }
      case "error": {
        set({ phase: "error", errorMessage: data.message ?? "unknown error" });
        break;
      }
    }
  },
}));
