import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiHeaders, resumeUrl, streamUrl } from "../../api/client";
import { streamSSE } from "../../api/sse";
import { GraphView } from "../graph/GraphView";
import { ApprovalModal } from "../hitl/ApprovalModal";
import { TimeTravelPanel } from "../history/TimeTravelPanel";
import { MessageLog } from "../stream/MessageLog";
import { useRunStore } from "../../state/runStore";

const PHASE_META: Record<string, { label: string; dot: string; text: string }> = {
  idle: { label: "Idle", dot: "bg-slate-500", text: "text-slate-300" },
  streaming: { label: "Running", dot: "bg-indigo-400", text: "text-indigo-200" },
  paused: { label: "Paused — awaiting human approval", dot: "bg-amber-400", text: "text-amber-200" },
  completed: { label: "Completed", dot: "bg-emerald-400", text: "text-emerald-200" },
  error: { label: "Error", dot: "bg-rose-400", text: "text-rose-200" },
};

export function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const startRun = useRunStore((s) => s.startRun);
  const applyEvent = useRunStore((s) => s.applyEvent);
  const appendSystemMessage = useRunStore((s) => s.appendSystemMessage);
  const phase = useRunStore((s) => s.phase);
  const log = useRunStore((s) => s.log);
  const pendingInterrupt = useRunStore((s) => s.pendingInterrupt);
  const errorMessage = useRunStore((s) => s.errorMessage);
  const startedForRunId = useRef<string | null>(null);
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    if (!runId || startedForRunId.current === runId) return;
    startedForRunId.current = runId;
    startRun(runId);

    streamSSE(streamUrl(runId), { headers: apiHeaders(false) }, applyEvent).catch((err) => {
      appendSystemMessage(`stream error: ${err instanceof Error ? err.message : String(err)}`);
    });
  }, [runId, startRun, applyEvent, appendSystemMessage]);

  async function handleResume(decision: "approve" | "reject" | "edit", editedContent?: string) {
    if (!runId) return;
    setResuming(true);
    try {
      await streamSSE(
        resumeUrl(runId),
        {
          method: "POST",
          headers: apiHeaders(),
          body: JSON.stringify({ decision, edited_content: editedContent ?? null }),
        },
        applyEvent
      );
    } catch (err) {
      appendSystemMessage(`resume error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setResuming(false);
    }
  }

  const meta = PHASE_META[phase];

  return (
    <div className="mx-auto min-h-screen w-full max-w-[1800px] px-10 py-10 2xl:px-16">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-indigo-300/80 transition-colors hover:text-indigo-200">
        ← All runs
      </Link>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="mt-3 mb-8 flex items-center justify-between"
      >
        <h1 className="truncate text-2xl font-medium text-slate-200">
          Run <span className="text-slate-500">{runId}</span>
        </h1>
        <span className="flex shrink-0 items-center gap-2.5 rounded-full border border-white/10 bg-white/[0.03] px-5 py-2 text-sm">
          <motion.span
            className={`h-2.5 w-2.5 rounded-full ${meta.dot}`}
            animate={phase === "streaming" || phase === "paused" ? { opacity: [1, 0.3, 1] } : { opacity: 1 }}
            transition={{ duration: 1.3, repeat: Infinity }}
          />
          <span className={meta.text}>{meta.label}</span>
        </span>
      </motion.div>

      <AnimatePresence>
        {phase === "error" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 overflow-hidden rounded-2xl border border-rose-500/25 bg-rose-500/5 p-5 text-sm text-rose-300"
          >
            {errorMessage}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid h-[calc(100vh-260px)] min-h-[36rem] grid-cols-1 gap-6 lg:grid-cols-2">
        <GraphView />
        <MessageLog entries={log} />
      </div>

      {runId && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }} className="mt-6">
          <TimeTravelPanel runId={runId} />
        </motion.div>
      )}

      {pendingInterrupt && (
        <ApprovalModal
          payload={pendingInterrupt}
          busy={resuming}
          onApprove={() => handleResume("approve")}
          onReject={() => handleResume("reject")}
          onEdit={(content) => handleResume("edit", content)}
        />
      )}
    </div>
  );
}
