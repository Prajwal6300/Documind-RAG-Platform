import React, { useState } from 'react';

export default function DebugPanel({ debug, groundedness }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!debug && !groundedness) return null;

  const score = groundedness?.score !== undefined ? Math.round(groundedness.score * 100) : null;
  const confidence = groundedness?.confidence || 'Medium';
  const badgeColor =
    confidence === 'High'
      ? 'bg-emerald-500/15 text-emerald-600 border-emerald-500/30'
      : confidence === 'Low'
      ? 'bg-error-container/20 text-error border-error/30'
      : 'bg-amber-500/15 text-amber-600 border-amber-500/30';

  return (
    <div className="mt-3 pt-3 border-t border-muted-text/10 text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {score !== null && (
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-[11px] font-semibold ${badgeColor}`}
              title="Evaluated groundedness and semantic overlap score"
            >
              <span className="material-symbols-outlined text-[14px]">verified</span>
              <span>Groundedness: {score}% ({confidence})</span>
            </span>
          )}
          {debug?.latency_ms && (
            <span className="text-muted-text text-[11px]">
              • {debug.latency_ms} ms
            </span>
          )}
        </div>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="inline-flex items-center gap-1 text-muted-text hover:text-coral-accent transition-colors font-label-md cursor-pointer"
        >
          <span className="material-symbols-outlined text-[16px]">
            {isOpen ? 'expand_less' : 'analytics'}
          </span>
          <span>{isOpen ? 'Hide Telemetry' : 'Inspect RAG Telemetry'}</span>
        </button>
      </div>

      {isOpen && (
        <div className="mt-3 p-4 bg-[#141311] rounded-xl border border-outline/20 text-[#E6E1D8] font-mono space-y-3 animate-in fade-in duration-200">
          <div className="flex flex-wrap gap-4 text-[11px] text-muted-text border-b border-white/10 pb-2">
            <div>
              <span className="opacity-60">Resolved Query: </span>
              <span className="text-white">{debug?.resolved_query || 'N/A'}</span>
            </div>
            <div>
              <span className="opacity-60">Candidates: </span>
              <span className="text-white">{debug?.retrieved_candidates ?? debug?.candidate_count ?? 0}</span>
            </div>
            <div>
              <span className="opacity-60">Re-ranked Top-K: </span>
              <span className="text-white">{debug?.final_context_chunks ?? (debug?.chunks?.length || 0)}</span>
            </div>
          </div>

          {debug?.chunks && debug.chunks.length > 0 && (
            <div>
              <span className="text-[11px] uppercase tracking-wider text-muted-text block mb-2 font-semibold">
                Re-ranked Context Chunks
              </span>
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {debug.chunks.map((c, i) => (
                  <div
                    key={i}
                    className="p-2.5 bg-black/40 rounded-lg border border-white/5 text-[11px] flex flex-col gap-1"
                  >
                    <div className="flex items-center justify-between text-coral-accent font-semibold">
                      <span>
                        Chunk #{i + 1} — {c.source} (Page {c.page || 1})
                      </span>
                      <span className="text-muted-text text-[10px]">
                        Rerank Score: {(c.rerank_score ?? c.final_score ?? 0).toFixed(3)}
                      </span>
                    </div>
                    <p className="text-white/80 text-[10px] line-clamp-2 leading-relaxed">
                      "{c.snippet}"
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
