import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { apiHeaders, getHistory, replayFromUrl, type CheckpointSummary } from "../../api/client";
import { streamSSE } from "../../api/sse";
import { useRunStore } from "../../state/runStore";

export function TimeTravelPanel({ runId }: { runId: string }) {
  const [checkpoints, setCheckpoints] = useState<CheckpointSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [replayingId, setReplayingId] = useState<string | null>(null);
  const startRun = useRunStore((s) => s.startRun);
  const applyEvent = useRunStore((s) => s.applyEvent);
  const appendSystemMessage = useRunStore((s) => s.appendSystemMessage);

  async function loadHistory() {
    setLoading(true);
    try {
      setCheckpoints(await getHistory(runId));
    } catch (err) {
      appendSystemMessage(`history error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  }

  async function replayFrom(checkpointId: string) {
    setReplayingId(checkpointId);
    startRun(runId);
    appendSystemMessage(`replaying from checkpoint ${checkpointId.slice(0, 8)}…`);
    try {
      await streamSSE(replayFromUrl(runId, checkpointId), { method: "POST", headers: apiHeaders() }, applyEvent);
    } catch (err) {
      appendSystemMessage(`replay error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setReplayingId(null);
    }
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 backdrop-blur-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5">
            <path d="M12 8v4l3 3M12 3a9 9 0 1 0 9 9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Time travel
        </h3>
        <motion.button
          whileHover={{ scale: loading ? 1 : 1.03 }}
          whileTap={{ scale: loading ? 1 : 0.97 }}
          onClick={loadHistory}
          disabled={loading}
          className="rounded-full border border-white/10 px-3.5 py-1.5 text-xs text-slate-300 transition-colors hover:border-indigo-400/40 hover:text-white disabled:opacity-50"
        >
          {loading ? "Loading…" : "Load checkpoint history"}
        </motion.button>
      </div>
      {checkpoints.length === 0 ? (
        <p className="text-xs text-slate-600">No history loaded yet.</p>
      ) : (
        <ul className="max-h-48 space-y-1.5 overflow-y-auto font-mono text-xs">
          <AnimatePresence>
            {checkpoints.map((cp, i) => (
              <motion.li
                key={cp.checkpoint_id}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.02 }}
                className="flex items-center justify-between gap-2 rounded-xl border border-white/5 bg-black/20 px-3 py-1.5"
              >
                <span className="truncate text-slate-400">
                  step {cp.step ?? "?"} · next: {cp.next.join(", ") || "(end)"} · {cp.checkpoint_id.slice(0, 8)}
                </span>
                <motion.button
                  whileHover={{ scale: replayingId ? 1 : 1.05 }}
                  whileTap={{ scale: replayingId ? 1 : 0.95 }}
                  onClick={() => replayFrom(cp.checkpoint_id)}
                  disabled={replayingId !== null}
                  className="shrink-0 rounded-full bg-indigo-500/90 px-2.5 py-1 text-white transition-colors hover:bg-indigo-400 disabled:opacity-50"
                >
                  {replayingId === cp.checkpoint_id ? "Replaying…" : "Replay from here"}
                </motion.button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
