import { Handle, Position } from "@xyflow/react";
import { motion } from "framer-motion";
import type { NodeStatusValue } from "../../types";

export interface AgentNodeData {
  label: string;
  status: NodeStatusValue | "idle";
  [key: string]: unknown;
}

const VARIANTS = {
  idle: {
    scale: 1,
    borderColor: "rgba(100,116,139,0.4)",
    background: "rgba(15,23,42,0.6)",
    boxShadow: "0 0 0px rgba(139,92,246,0)",
    color: "#94a3b8",
  },
  started: {
    scale: 1.06,
    borderColor: "rgba(167,139,250,0.9)",
    background: "rgba(76,29,149,0.35)",
    boxShadow: "0 0 22px rgba(139,92,246,0.55)",
    color: "#e9d5ff",
  },
  waiting: {
    scale: 1.06,
    borderColor: "rgba(251,191,36,0.9)",
    background: "rgba(120,53,15,0.3)",
    boxShadow: "0 0 22px rgba(251,191,36,0.5)",
    color: "#fde68a",
  },
  completed: {
    scale: 1,
    borderColor: "rgba(52,211,153,0.6)",
    background: "rgba(6,78,59,0.3)",
    boxShadow: "0 0 0px rgba(52,211,153,0)",
    color: "#6ee7b7",
  },
};

export function AgentNode({ data }: { data: AgentNodeData }) {
  const status = data.status ?? "idle";
  const isActive = status === "started" || status === "waiting";

  return (
    <motion.div
      animate={status}
      variants={VARIANTS}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      style={{ borderWidth: 1.5, borderStyle: "solid" }}
      className="rounded-xl px-3.5 py-2.5 text-center text-xs font-medium backdrop-blur-sm"
    >
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-0 !bg-slate-500" />
      <span className="relative">
        {data.label}
        {isActive && (
          <motion.span
            className="absolute -right-3 -top-1 h-1.5 w-1.5 rounded-full bg-current"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
          />
        )}
      </span>
      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-0 !bg-slate-500" />
    </motion.div>
  );
}
