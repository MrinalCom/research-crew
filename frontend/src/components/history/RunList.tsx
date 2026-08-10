import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createRun, listRuns, type RunSummary } from "../../api/client";

const STATUS_STYLES: Record<RunSummary["status"], string> = {
  running: "bg-indigo-500/15 text-indigo-300 ring-1 ring-inset ring-indigo-400/30",
  paused: "bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-400/30",
  completed: "bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-400/30",
  failed: "bg-rose-500/15 text-rose-300 ring-1 ring-inset ring-rose-400/30",
};

const EXAMPLE_TASKS = [
  "Write a Python function that validates ISBN-13 codes, with tests.",
  "Reverse a linked list in Python, with edge-case tests.",
  "Check if a string is a palindrome, ignoring case and punctuation.",
];

export function RunList() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [task, setTask] = useState("");
  const [maxRevisions, setMaxRevisions] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function refresh() {
    try {
      setRuns(await listRuns());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!task.trim()) return;
    setLoading(true);
    try {
      const run = await createRun(task.trim(), maxRevisions);
      navigate(`/runs/${run.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full flex-col items-center px-6 py-20">
      <div className="flex w-full max-w-4xl flex-1 flex-col items-center justify-center">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mb-12 flex flex-col items-center text-center"
        >
          <div className="mb-5 flex items-center gap-4">
            <motion.span
              className="h-14 w-14 rounded-full bg-gemini-gradient"
              animate={{ boxShadow: ["0 0 0px rgba(139,92,246,0)", "0 0 40px rgba(139,92,246,0.6)", "0 0 0px rgba(139,92,246,0)"] }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            />
            <h1 className="gradient-text text-5xl font-semibold tracking-tight sm:text-6xl">Research Crew</h1>
          </div>
          <p className="max-w-xl text-lg leading-relaxed text-slate-400">
            A supervisor-led multi-agent crew — plan, research, code, review, approve.
            <br />
            Watch it think, live.
          </p>
        </motion.div>

        <motion.form
          onSubmit={handleCreate}
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="w-full rounded-[32px] border border-white/10 bg-white/[0.03] p-7 shadow-2xl shadow-black/40 backdrop-blur-xl"
        >
          <label className="mb-3 block text-xs font-medium uppercase tracking-wider text-slate-500">
            What should the crew build?
          </label>
          <textarea
            className="w-full resize-none rounded-3xl border border-white/10 bg-black/20 p-5 text-lg text-slate-100 placeholder:text-slate-500 transition-colors focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            rows={4}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder={EXAMPLE_TASKS[0]}
          />

          <div className="mt-4 flex flex-wrap gap-2">
            {EXAMPLE_TASKS.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setTask(example)}
                className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-1.5 text-sm text-slate-400 transition-colors hover:border-indigo-400/40 hover:text-slate-200"
              >
                {example.length > 46 ? example.slice(0, 46) + "…" : example}
              </button>
            ))}
          </div>

          <div className="mt-7 flex items-end justify-between gap-4">
            <label className="text-xs font-medium uppercase tracking-wider text-slate-500">
              Max revisions
              <input
                type="number"
                min={0}
                max={10}
                className="mt-1.5 block w-24 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-base text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                value={maxRevisions}
                onChange={(e) => setMaxRevisions(Number(e.target.value))}
              />
            </label>

            <motion.button
              type="submit"
              disabled={loading || !task.trim()}
              whileHover={{ scale: loading || !task.trim() ? 1 : 1.02 }}
              whileTap={{ scale: loading || !task.trim() ? 1 : 0.97 }}
              className="relative overflow-hidden rounded-full bg-gemini-gradient px-8 py-3.5 text-base font-medium text-white shadow-lg shadow-indigo-950/40 disabled:opacity-40"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <motion.span
                    className="h-4 w-4 rounded-full border-2 border-white/40 border-t-white"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
                  />
                  Starting…
                </span>
              ) : (
                "Start run"
              )}
            </motion.button>
          </div>

          <AnimatePresence>
            {error && (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 text-sm text-rose-400"
              >
                {error}
              </motion.p>
            )}
          </AnimatePresence>
        </motion.form>
      </div>

      {runs.length > 0 && (
        <div className="mt-16 w-full max-w-4xl">
          <motion.h2
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15 }}
            className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500"
          >
            Past runs
          </motion.h2>
          <div className="space-y-2">
            <AnimatePresence>
              {runs.map((run, i) => (
                <motion.button
                  key={run.run_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.04 }}
                  whileHover={{ x: 2 }}
                  onClick={() => navigate(`/runs/${run.run_id}`)}
                  className="flex w-full items-center justify-between rounded-2xl border border-white/10 bg-white/[0.02] px-5 py-4 text-left transition-colors hover:border-indigo-400/30 hover:bg-white/[0.04]"
                >
                  <span className="truncate text-base text-slate-200">{run.task}</span>
                  <span className={`ml-4 shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[run.status]}`}>
                    {run.status}
                  </span>
                </motion.button>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
