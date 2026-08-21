import React, { useState, forwardRef } from 'react';

const EvidenceCard = forwardRef(function EvidenceCard(
  { evidence, isInitiallyOpen = true, isHighlighted = false },
  ref
) {
  const [isOpen, setIsOpen] = useState(isInitiallyOpen);

  return (
    <div
      ref={ref}
      id={evidence.id}
      className={`pt-2 transition-all duration-300 rounded-xl ${
        isHighlighted ? 'ring-2 ring-coral-accent ring-offset-4 ring-offset-canvas' : ''
      }`}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 text-coral-accent text-label-md font-label-md hover:opacity-80 transition-opacity mb-3 group cursor-pointer"
        aria-expanded={isOpen}
      >
        <span
          className={`material-symbols-outlined text-sm transition-transform duration-200 ${
            isOpen ? 'rotate-0' : '-rotate-90'
          }`}
        >
          arrow_drop_down
        </span>
        <span className="group-hover:underline">
          {isOpen ? 'Hide evidence' : 'View evidence'}
        </span>
      </button>

      {isOpen && (
        <div className="bg-[#181715] rounded-xl p-6 shadow-sm border border-outline/20 animate-in fade-in duration-200">
          <div className="flex flex-wrap items-center gap-4 mb-4 text-label-sm font-label-sm text-[#EFE9DE] opacity-75">
            <span className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-coral-accent">folder</span>
              <span className="uppercase tracking-wider">DOCUMENT:</span>
              <span className="font-semibold text-white">{evidence.docName}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-coral-accent">find_in_page</span>
              <span className="uppercase tracking-wider">PAGE:</span>
              <span className="font-semibold text-white">{evidence.page}</span>
            </span>
            {evidence.docType && (
              <span className="flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[16px] text-coral-accent">category</span>
                <span className="uppercase tracking-wider">TYPE:</span>
                <span className="font-semibold text-white capitalize">{evidence.docType.replaceAll('_', ' ')}</span>
              </span>
            )}
          </div>
          {evidence.docSummary && (
            <p className="text-xs text-[#EFE9DE] opacity-75 mb-4 leading-relaxed">
              {evidence.docSummary}
            </p>
          )}

          <div className="text-body-md font-body-md text-canvas font-mono leading-relaxed pl-4 border-l-2 border-coral-accent bg-[#181715]/60 py-1">
            "{evidence.quote}"
          </div>
        </div>
      )}
    </div>
  );
});

export default EvidenceCard;
