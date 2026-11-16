"use client";

import { useEffect, useRef } from "react";
import { Terminal as TerminalIcon, Trash2 } from "lucide-react";

export interface LogEntry {
  timestamp: string;
  type: "info" | "success" | "warn" | "error";
  message: string;
}

interface TerminalConsoleProps {
  logs: LogEntry[];
  onClear: () => void;
}

export function TerminalConsole({ logs, onClear }: TerminalConsoleProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const getColorClass = (type: LogEntry["type"]) => {
    switch (type) {
      case "success":
        return "text-emerald-400";
      case "warn":
        return "text-amber-400";
      case "error":
        return "text-rose-400 font-semibold";
      default:
        return "text-sky-300";
    }
  };

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl flex flex-col h-[480px]">
      {/* Barra de título do terminal */}
      <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 mr-2">
            <span className="w-3 h-3 rounded-full bg-rose-500/80 inline-block" />
            <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
            <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
          </div>
          <TerminalIcon className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-mono font-medium text-slate-300">
            Console de Eventos & Logs Operacionais
          </span>
        </div>
        <button
          onClick={onClear}
          className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 px-2 py-1 rounded bg-slate-800/60 hover:bg-slate-800 transition-colors"
          title="Limpar logs"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Limpar
        </button>
      </div>

      {/* Janela de saída de logs */}
      <div className="flex-1 p-4 font-mono text-xs overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-slate-800">
        {logs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-600 italic">
            Nenhum gatilho disparado ainda. Aguardando comandos...
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="flex items-start gap-2 leading-relaxed">
              <span className="text-slate-500 select-none">[{log.timestamp}]</span>
              <span className="select-none font-bold uppercase text-[10px] tracking-wider px-1 rounded bg-slate-900 border border-slate-800">
                {log.type}
              </span>
              <span className={`flex-1 break-all ${getColorClass(log.type)}`}>
                {log.message}
              </span>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}

