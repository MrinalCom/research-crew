import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import type { InterruptPayload } from "../../types";

interface Props {
  payload: InterruptPayload;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onEdit: (content: string) => void;
}

export function ApprovalModal({ payload, busy, onApprove, onReject, onEdit }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(payload.artifact?.content ?? "");

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 8 }}
          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          className="max-h-[85vh] w-full max-w-4xl overflow-y-auto rounded-3xl border border-amber-400/20 bg-[#0d0e16]/95 p-9 shadow-2xl shadow-black/60 backdrop-blur-2xl"
        >
          <div className="mb-1 flex items-center gap-2">
            <motion.span
              className="h-2 w-2 rounded-full bg-amber-400"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.4, repeat: Infinity }}
            />
            <h2 className="text-lg font-semibold text-amber-200">Approval needed</h2>
          </div>
          <p className="mb-5 text-sm text-slate-400">{payload.task}</p>

          {payload.review_history.length > 0 && (
            <div className="mb-5 space-y-1.5">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">Review history</h3>
              {payload.review_history.map((v, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={`rounded-xl border px-3 py-1.5 text-xs ${
                    v.approved ? "border-emerald-500/25 bg-emerald-500/5 text-emerald-300" : "border-rose-500/25 bg-rose-500/5 text-rose-300"
                  }`}
                >
                  {v.approved ? "Approved" : "Rejected"} ({v.target_artifact_id}) — {v.feedback}
                </motion.div>
              ))}
            </div>
          )}

          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Artifact: {payload.artifact?.id ?? "(none)"}
            {payload.artifact && ` · ${payload.artifact.kind} · v${payload.artifact.version} · by ${payload.artifact.author}`}
          </h3>

          <AnimatePresence mode="wait">
            {editing ? (
              <motion.textarea
                key="editor"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="mb-5 h-64 w-full rounded-2xl border border-white/10 bg-black/30 p-4 font-mono text-xs text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
            ) : (
              <motion.pre
                key="viewer"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="mb-5 max-h-64 overflow-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-black/30 p-4 font-mono text-xs text-slate-300"
              >
                {payload.artifact?.content ?? "(no artifact)"}
              </motion.pre>
            )}
          </AnimatePresence>

          <div className="flex flex-wrap gap-2">
            {!editing && (
              <>
                <motion.button
                  whileHover={{ scale: busy ? 1 : 1.03 }}
                  whileTap={{ scale: busy ? 1 : 0.97 }}
                  disabled={busy}
                  onClick={onApprove}
                  className="rounded-full bg-emerald-500 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-emerald-950/40 disabled:opacity-50"
                >
                  Approve
                </motion.button>
                <motion.button
                  whileHover={{ scale: busy ? 1 : 1.03 }}
                  whileTap={{ scale: busy ? 1 : 0.97 }}
                  disabled={busy}
                  onClick={onReject}
                  className="rounded-full bg-rose-500 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-rose-950/40 disabled:opacity-50"
                >
                  Reject
                </motion.button>
                <motion.button
                  whileHover={{ scale: busy || !payload.artifact ? 1 : 1.03 }}
                  whileTap={{ scale: busy || !payload.artifact ? 1 : 0.97 }}
                  disabled={busy || !payload.artifact}
                  onClick={() => setEditing(true)}
                  className="rounded-full border border-white/15 px-5 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:bg-white/5 disabled:opacity-50"
                >
                  Edit
                </motion.button>
              </>
            )}
            {editing && (
              <>
                <motion.button
                  whileHover={{ scale: busy ? 1 : 1.03 }}
                  whileTap={{ scale: busy ? 1 : 0.97 }}
                  disabled={busy}
                  onClick={() => onEdit(draft)}
                  className="rounded-full bg-gemini-gradient px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-950/40 disabled:opacity-50"
                >
                  Submit edited version
                </motion.button>
                <motion.button
                  whileHover={{ scale: busy ? 1 : 1.03 }}
                  whileTap={{ scale: busy ? 1 : 0.97 }}
                  disabled={busy}
                  onClick={() => setEditing(false)}
                  className="rounded-full border border-white/15 px-5 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:bg-white/5 disabled:opacity-50"
                >
                  Cancel
                </motion.button>
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
