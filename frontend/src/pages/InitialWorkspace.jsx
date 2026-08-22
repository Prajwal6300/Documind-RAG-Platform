import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function InitialWorkspace() {
  const navigate = useNavigate();
  const {
    sendChatMessage,
    setIsUploadModalOpen,
    addToast,
    documents,
    suggestedQuestions,
    selectedScope,
    setSelectedScope,
    recentlyUploadedDocId,
  } = useApp();

  const [query, setQuery] = useState('');
  const [isAttachmentOpen, setIsAttachmentOpen] = useState(false);
  const [isScopeDropdownOpen, setIsScopeDropdownOpen] = useState(false);

  const attachmentRef = useRef(null);
  const scopeRef = useRef(null);

  const activeDocs = documents.filter((d) => d.status === 'Indexed' || d.status === 'Processing' || d.status === 'Uploading');
  const indexedDocs = documents.filter((d) => d.status === 'Indexed');

  // Close menus on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (attachmentRef.current && !attachmentRef.current.contains(e.target)) {
        setIsAttachmentOpen(false);
      }
      if (scopeRef.current && !scopeRef.current.contains(e.target)) {
        setIsScopeDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchSubmit = (e) => {
    e?.preventDefault();
    if (!query.trim()) {
      addToast('Please enter a question about your documents.', 'info');
      return;
    }
    sendChatMessage(query.trim(), selectedScope);
    navigate('/chat');
  };

  const handleSuggestedClick = (question) => {
    sendChatMessage(question.prompt || question.title, selectedScope);
    navigate('/chat');
  };

  const handleCategoryChip = (category) => {
    if (indexedDocs.length === 0) {
      addToast('Please upload a document first before asking questions.', 'info');
      return;
    }
    const docName = indexedDocs[0]?.name || 'the uploaded document';
    if (category === 'Summarize') {
      setQuery(`Summarize key findings and main takeaways from ${docName}`);
    } else if (category === 'Compare') {
      if (indexedDocs.length >= 2) {
        setQuery(`Compare key topics and differences between ${indexedDocs[0].name} and ${indexedDocs[1].name}`);
      } else {
        setQuery(`Compare key sections and policies within ${docName}`);
      }
    } else if (category === 'Analyze') {
      setQuery(`Analyze potential risks, requirements, and key terms in ${docName}`);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-center max-w-content-max-width mx-auto px-margin-mobile md:px-margin-desktop py-12 min-h-[calc(100vh-5rem)]">
      {/* Hero Text */}
      <div className="text-center mb-10 max-w-3xl mx-auto animate-in fade-in slide-in-from-bottom-2 duration-300">
        <h1 className="font-display-lg text-headline-lg md:text-display-lg text-on-surface mb-4 font-semibold tracking-tight">
          ✦ What would you like to know about your documents?
        </h1>
        <p className="font-body-lg text-body-md md:text-body-lg text-muted-text max-w-2xl mx-auto leading-relaxed">
          {activeDocs.length > 0
            ? `Ask questions across your ${activeDocs.length} ${activeDocs.length === 1 ? 'document' : 'documents'}. DocuMind retrieves strictly grounded evidence using Gemini.`
            : 'Upload PDF, DOCX, or TXT documents to start asking questions grounded strictly in your files.'}
        </p>
      </div>

      {/* Recently uploaded banner */}
      {recentlyUploadedDocId && (
        <div className="max-w-4xl mx-auto w-full mb-4 px-4 py-2.5 bg-coral-accent/10 border border-coral-accent/30 rounded-xl flex items-center justify-between text-xs text-coral-accent font-label-md animate-in fade-in slide-in-from-top-1 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px]">check_circle</span>
            <span>
              Document added! Search scope automatically targeted to <strong>"{selectedScope}"</strong>.
            </span>
          </div>
          <button
            onClick={() => navigate('/library')}
            className="hover:underline font-semibold cursor-pointer shrink-0 ml-2"
          >
            View in Library →
          </button>
        </div>
      )}

      {/* If 0 documents exist: Empty State CTA */}
      {documents.length === 0 ? (
        <div className="max-w-2xl mx-auto w-full mb-10 text-center p-8 bg-card-surface/40 rounded-2xl border-2 border-dashed border-outline/30 animate-in fade-in">
          <span className="material-symbols-outlined text-[48px] text-coral-accent mb-3">
            cloud_upload
          </span>
          <h2 className="text-headline-md font-headline-md text-on-surface mb-2 font-semibold">
            No Documents Uploaded Yet
          </h2>
          <p className="text-body-md text-muted-text max-w-md mx-auto mb-6">
            DocuMind answers questions grounded solely in your uploaded files. Upload your first PDF, DOCX, or TXT file to begin.
          </p>
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-coral-accent text-white font-label-md hover:bg-primary transition-all shadow-sm cursor-pointer active:scale-95"
          >
            <span className="material-symbols-outlined text-[20px]">upload_file</span>
            <span>Upload Your First Document</span>
          </button>
        </div>
      ) : (
        /* Search Input Area */
        <div className="relative w-full max-w-4xl mx-auto mb-10">
          <div className="absolute inset-0 bg-canvas rounded-2xl shadow-[0_4px_24px_rgba(27,28,26,0.08)] pointer-events-none" />
          <form
            onSubmit={handleSearchSubmit}
            className="relative flex items-center bg-canvas h-search-height rounded-2xl px-4 border border-outline/15 focus-within:border-coral-accent/60 focus-within:ring-2 focus-within:ring-coral-accent/20 transition-all shadow-sm"
          >
            {/* Attachment trigger & dropdown */}
            <div className="relative" ref={attachmentRef}>
              <button
                type="button"
                onClick={() => setIsAttachmentOpen(!isAttachmentOpen)}
                className="p-2 text-muted-text hover:text-coral-accent transition-colors flex items-center justify-center rounded-lg hover:bg-surface-container mr-1 cursor-pointer"
                title="Attach file"
                aria-label="Attach file"
                aria-expanded={isAttachmentOpen}
              >
                <span className="material-symbols-outlined text-[22px]">attach_file</span>
              </button>

              {isAttachmentOpen && (
                <div className="absolute bottom-full left-0 mb-2 w-48 bg-surface-container-low border border-outline/15 rounded-xl shadow-xl overflow-hidden z-50 animate-in fade-in slide-in-from-bottom-2">
                  <div className="flex flex-col p-1.5 gap-0.5">
                    <button
                      type="button"
                      onClick={() => {
                        setIsAttachmentOpen(false);
                        setIsUploadModalOpen(true);
                      }}
                      className="flex items-center gap-3 px-3.5 py-2 text-left hover:bg-surface-container-highest transition-colors rounded-lg group text-sm font-label-md cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-muted-text group-hover:text-coral-accent text-[20px]">
                        upload_file
                      </span>
                      <span className="text-on-surface">Upload Document</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Input field */}
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask anything about your documents..."
              className="flex-1 h-full bg-transparent border-none focus:ring-0 font-body-lg text-body-md md:text-body-lg text-on-surface placeholder:text-muted-text/70 px-2"
            />

            {/* Right controls: Scope Dropdown & Submit Button */}
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Scope selector */}
              <div className="relative" ref={scopeRef}>
                <button
                  type="button"
                  onClick={() => setIsScopeDropdownOpen(!isScopeDropdownOpen)}
                  className="hidden sm:flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-container-low text-muted-text font-label-md text-xs sm:text-sm hover:bg-surface-container-highest transition-colors border border-outline/10"
                  aria-expanded={isScopeDropdownOpen}
                >
                  <span className="truncate max-w-[120px]">{selectedScope}</span>
                  <span className="material-symbols-outlined text-[16px]">arrow_drop_down</span>
                </button>

                {isScopeDropdownOpen && (
                  <div className="absolute top-full right-0 mt-2 w-64 bg-card-surface border border-outline/20 rounded-xl shadow-xl py-1.5 z-50 animate-in fade-in">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedScope('All Documents');
                        setIsScopeDropdownOpen(false);
                      }}
                      className="w-full flex items-center justify-between px-3.5 py-2 text-left text-xs font-label-md text-on-surface hover:bg-surface-container transition-colors"
                    >
                      <span>All Documents ({indexedDocs.length})</span>
                      {selectedScope === 'All Documents' && (
                        <span className="material-symbols-outlined text-[16px] text-coral-accent">check</span>
                      )}
                    </button>
                    {indexedDocs.map((doc) => (
                      <button
                        key={doc.id}
                        type="button"
                        onClick={() => {
                          setSelectedScope(doc.name);
                          setIsScopeDropdownOpen(false);
                        }}
                        className="w-full flex items-center justify-between px-3.5 py-1.5 text-left text-xs font-label-md text-on-surface hover:bg-surface-container transition-colors"
                      >
                        <span className="truncate pr-2">{doc.name}</span>
                        {selectedScope === doc.name && (
                          <span className="material-symbols-outlined text-[16px] text-coral-accent">check</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Upward Submit Button */}
              <button
                type="submit"
                className="w-10 h-10 rounded-full bg-coral-accent text-on-primary flex items-center justify-center hover:bg-primary transition-all shadow-sm active:scale-95 cursor-pointer"
                title="Submit prompt"
                aria-label="Submit prompt"
              >
                <span className="material-symbols-outlined font-bold text-[20px]">arrow_upward</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Suggested Questions Grid (Only rendered if questions exist) */}
      {suggestedQuestions.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl mx-auto w-full mb-10">
          {suggestedQuestions.map((q) => (
            <button
              key={q.id}
              onClick={() => handleSuggestedClick(q)}
              className="text-left bg-card-surface p-5 rounded-xl hover:bg-surface-container-highest transition-all duration-200 group flex flex-col justify-between min-h-[105px] border border-outline-variant/20 hover:border-coral-accent/40 hover:shadow-xs cursor-pointer"
            >
              <span className="font-headline-md text-headline-md text-on-surface group-hover:text-primary transition-colors leading-snug">
                {q.title}
              </span>
              <div className="flex items-center justify-between mt-3">
                <span className="font-label-sm text-xs text-muted-text opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-coral-accent">
                  <span>Click to ask</span>
                  <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                </span>
                <span className="material-symbols-outlined text-muted-text/40 group-hover:text-coral-accent text-[18px]">
                  auto_awesome
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Category Chips (Only if documents exist) */}
      {indexedDocs.length > 0 && (
        <div className="flex justify-center items-center gap-3 flex-wrap">
          {['Summarize', 'Compare', 'Analyze'].map((cat) => (
            <button
              key={cat}
              onClick={() => handleCategoryChip(cat)}
              className="px-4 py-1.5 rounded-full border border-outline/20 text-muted-text font-label-md text-xs sm:text-sm hover:border-coral-accent hover:text-coral-accent transition-colors bg-surface/50 cursor-pointer active:scale-95"
            >
              {cat}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
