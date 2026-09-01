import React from 'react';

export default function CitationBadge({ citation, onCitationClick }) {
  if (!citation) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => onCitationClick?.(citation.evidenceId)}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-surface-container-highest 
                   text-label-sm font-label-sm text-secondary cursor-pointer 
                   hover:bg-coral-accent hover:text-white transition-colors duration-150 shadow-2xs"
        title={`${citation.docName}${citation.docType ? ` · ${citation.docType.replaceAll('_', ' ')}` : ''}${citation.docSummary ? ` · ${citation.docSummary}` : ''}`}
        aria-label={`View evidence from ${citation.docName} page ${citation.page}`}
      >
        <span className="material-symbols-outlined text-[14px]">find_in_page</span>
        <span>{citation.label}</span>
      </button>
    </div>
  );
}
#documind
