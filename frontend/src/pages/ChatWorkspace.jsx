import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import EvidenceCard from '../components/chat/EvidenceCard';
import CitationBadge from '../components/chat/CitationBadge';
import DebugPanel from '../components/chat/DebugPanel';

export default function ChatWorkspace() {
  const navigate = useNavigate();
  const {
    chatMessages,
    sendChatMessage,
    isAiThinking,
    startNewChat,
    documents,
    selectedScope,
  } = useApp();

  const [followUpText, setFollowUpText] = useState('');
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState(null);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [logs, setLogs] = useState([]);
  const chatBottomRef = useRef(null);

  const indexedDocs = documents.filter((d) => d.status === 'Indexed');

  const scrollToBottom = () => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages, isAiThinking]);

  const handleCitationClick = (evidenceId) => {
    if (!evidenceId) return;
    setHighlightedEvidenceId(evidenceId);
    const element = document.getElementById(evidenceId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    setTimeout(() => {
      setHighlightedEvidenceId(null);
    }, 2500);
  };

  const handleSendFollowUp = (e) => {
    e?.preventDefault();
    if (!followUpText.trim()) return;
    sendChatMessage(followUpText);
    setFollowUpText('');
  };

  const handleOpenLogs = async () => {
    setShowLogsModal(true);
    try {
      const res = await fetch('/api/logs?lines=40');
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  };

  return (
    <div className="flex-1 flex flex-col relative h-[calc(100vh-4rem)] overflow-hidden">
      {/* Top action bar: Active scope & New conversation & Telemetry */}
      <div className="flex items-center justify-between px-margin-mobile md:px-margin-desktop py-2.5 bg-background/60 border-b border-outline-variant/10 text-xs text-muted-text">
        <span className="font-label-sm">
          Active Context:{' '}
          <strong className="text-on-surface font-semibold">
            {selectedScope === 'All Documents'
              ? `${indexedDocs.length} Indexed ${indexedDocs.length === 1 ? 'File' : 'Files'}`
              : `Scoped to "${selectedScope}"`}
          </strong>
        </span>
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpenLogs}
            className="flex items-center gap-1 text-muted-text hover:text-coral-accent transition-colors font-label-md cursor-pointer"
            title="View live structured pipeline logs"
          >
            <span className="material-symbols-outlined text-[16px]">terminal</span>
            <span>Pipeline Logs</span>
          </button>
          <button
            onClick={startNewChat}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-coral-accent hover:bg-surface-container transition-colors font-label-md cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px]">restart_alt</span>
            <span>New Thread</span>
          </button>
        </div>
      </div>

      {/* Chat Feed Scroll Area */}
      <div className="flex-1 overflow-y-auto w-full flex justify-center pb-36 pt-6 px-margin-mobile md:px-margin-desktop scroll-smooth">
        <div className="w-full max-w-content-max-width space-y-10">
          {chatMessages.length === 0 && !isAiThinking && (
            <div className="text-center py-20 text-muted-text">
              <span className="material-symbols-outlined text-[44px] text-coral-accent/60 mb-3">
                chat_bubble_outline
              </span>
              <h2 className="text-headline-md font-headline-md text-on-surface font-medium mb-1">
                Conversation Workspace
              </h2>
              <p className="text-sm text-muted-text max-w-md mx-auto mb-4">
                Ask any question below. Answers will be strictly retrieved and cited from your indexed documents.
              </p>
              <button
                onClick={() => navigate('/')}
                className="text-xs text-coral-accent hover:underline font-label-md inline-flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[14px]">arrow_back</span>
                <span>Return to Workspace Prompts</span>
              </button>
            </div>
          )}

          {chatMessages.map((msg) => {
            if (msg.sender === 'user') {
              return (
                <div key={msg.id} className="flex justify-end animate-in fade-in slide-in-from-bottom-1 duration-200">
                  <div className="max-w-2xl bg-surface-container-low px-6 py-4 rounded-2xl rounded-tr-xs border border-muted-text/15 shadow-xs">
                    <p className="text-body-lg font-body-lg text-on-surface whitespace-pre-wrap">
                      {msg.text}
                    </p>
                    <span className="block text-right text-[11px] text-muted-text mt-1.5 font-label-sm">
                      {msg.timestamp}
                    </span>
                  </div>
                </div>
              );
            }

            return (
              <div key={msg.id} className="space-y-6 animate-in fade-in duration-300">
                {/* Assistant editorial response */}
                <div className="text-body-lg font-body-lg text-body-text leading-relaxed">
                  {msg.intro && <p className="mb-4 whitespace-pre-wrap">{msg.intro}</p>}

                  {(!msg.sections || msg.sections.length === 0) && msg.text && msg.text !== msg.intro && (
                    <p className="mb-4 whitespace-pre-wrap">{msg.text}</p>
                  )}

                  {msg.sections?.map((sec, sIdx) => (
                    <div key={sIdx} className="mt-6 mb-4">
                      {sec.heading && (
                        <h3 className="text-headline-md font-headline-md text-on-surface font-semibold mb-3">
                          {sec.heading}
                        </h3>
                      )}
                      <ul className="space-y-4 list-disc pl-5 marker:text-coral-accent">
                        {sec.items?.map((item, iIdx) => (
                          <li key={iIdx} className="pl-1">
                            {item.title && (
                              <strong className="text-on-surface font-medium">{item.title}: </strong>
                            )}
                            <span>{item.description}</span>
                            {item.citation && (
                              <CitationBadge
                                citation={item.citation}
                                onCitationClick={handleCitationClick}
                              />
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>

                {/* Sources Section */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="pt-5 border-t border-muted-text/15">
                    <h4 className="text-label-md font-label-md text-muted-text mb-3 uppercase tracking-wider text-xs font-semibold">
                      Sources Cited
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {msg.sources.map((src, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleCitationClick(src.evidenceId)}
                          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-muted-text/20 
                                     text-body-md text-xs sm:text-sm text-secondary hover:border-coral-accent hover:text-coral-accent 
                                     transition-colors cursor-pointer bg-surface/50"
                        >
                          <span className="material-symbols-outlined text-[16px]">description</span>
                          <span>{src.name} · Page {src.page}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Evidences List */}
                {msg.evidences && msg.evidences.length > 0 && (
                  <div className="space-y-3 pt-2">
                    {msg.evidences.map((evidence) => (
                      <EvidenceCard
                        key={evidence.id}
                        evidence={evidence}
                        isHighlighted={highlightedEvidenceId === evidence.id}
                      />
                    ))}
                  </div>
                )}

                {/* Observability Telemetry Drawer */}
                <DebugPanel debug={msg.debug} groundedness={msg.groundedness} />
              </div>
            );
          })}

          {/* AI Thinking Animation */}
          {isAiThinking && (
            <div className="flex items-center gap-3 text-muted-text animate-pulse p-4 rounded-xl bg-card-surface/50 border border-outline/10">
              <span className="material-symbols-outlined animate-spin text-coral-accent">
                progress_activity
              </span>
              <span className="text-sm font-label-md">
                DocuMind is retrieving vector embeddings, re-ranking with CrossEncoder, & synthesizing response with Gemini...
              </span>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>
      </div>

      {/* Fixed Search Bar Area at Bottom */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-canvas via-canvas/95 to-transparent pb-6 pt-10 px-margin-mobile md:px-margin-desktop flex justify-center z-20">
        <form
          onSubmit={handleSendFollowUp}
          className="w-full max-w-content-max-width relative shadow-[0_8px_30px_rgb(0,0,0,0.08)] rounded-2xl group"
        >
          <input
            type="text"
            value={followUpText}
            onChange={(e) => setFollowUpText(e.target.value)}
            placeholder="Ask a follow-up question..."
            disabled={isAiThinking}
            className="w-full h-search-height bg-canvas border border-muted-text/25 rounded-2xl pl-6 pr-16 
                       text-body-lg font-body-lg text-on-surface placeholder:text-muted-text 
                       focus:outline-none focus:border-coral-accent focus:ring-2 focus:ring-coral-accent/20 
                       transition-all disabled:opacity-60 shadow-sm"
          />
          <button
            type="submit"
            disabled={!followUpText.trim() || isAiThinking}
            className="absolute right-3.5 top-1/2 -translate-y-1/2 p-2.5 rounded-xl bg-coral-accent text-white 
                       hover:bg-primary transition-all disabled:opacity-40 disabled:hover:bg-coral-accent 
                       shadow-xs active:scale-95 cursor-pointer"
            aria-label="Send message"
          >
            <span className="material-symbols-outlined text-[20px]">send</span>
          </button>
        </form>
      </div>

      {/* Pipeline Logs Modal */}
      {showLogsModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-canvas/70 backdrop-blur-sm animate-in fade-in"
          role="dialog"
        >
          <div className="bg-[#141311] border border-outline/30 rounded-2xl w-full max-w-3xl max-h-[80vh] flex flex-col shadow-2xl overflow-hidden font-mono text-xs">
            <div className="px-6 py-4 border-b border-white/10 flex justify-between items-center text-white">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-coral-accent text-[18px]">terminal</span>
                <span className="font-semibold text-sm">Pipeline Observability Telemetry Logs</span>
              </div>
              <button
                onClick={() => setShowLogsModal(false)}
                className="text-white/60 hover:text-white p-1"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-1 text-emerald-400 bg-black/60">
              {logs.length === 0 ? (
                <p className="text-muted-text">No pipeline logs available yet.</p>
              ) : (
                logs.map((line, idx) => (
                  <div key={idx} className="whitespace-pre-wrap leading-relaxed">
                    {line}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
