import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef } from "react";
import type { LogEntry } from "../../state/runStore";

const KIND_STYLES: Record<LogEntry["kind"], string> = {
  status: "text-indigo-300",
  token: "text-slate-200",
  system: "text-amber-300 italic",
};

const KIND_DOT: Record<LogEntry["kind"], string> = {
  status: "bg-indigo-400",
  token: "bg-slate-500",
  system: "bg-amber-400",
};

export function MessageLog({ entries }: { entries: LogEntry[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  return (
    <div className="flex h-full flex-col overflow-y-auto rounded-2xl border border-white/10 bg-white/[0.02] p-4 font-mono text-[13px] backdrop-blur-sm">
      {entries.length === 0 && <p className="text-slate-600">No activity yet.</p>}
      <AnimatePresence initial={false}>
        {entries.map((entry) => (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="mb-1.5 flex items-start gap-2 leading-snug"
          >
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${KIND_DOT[entry.kind]}`} />
            <span>
              <span className="mr-2 text-xs text-slate-600">[{entry.node}]</span>
              <span className={KIND_STYLES[entry.kind]}>{entry.text}</span>
            </span>
          </motion.div>
        ))}
      </AnimatePresence>
      <div ref={bottomRef} />
    </div>
  );
}
