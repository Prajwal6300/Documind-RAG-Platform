import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function RecentAnalysisPage() {
  const navigate = useNavigate();
  const { recentAnalyses, loadChatSession, addToast } = useApp();
  const [searchTerm, setSearchTerm] = useState('');

  const filteredAnalyses = useMemo(() => {
    if (!searchTerm.trim()) return recentAnalyses;
    return recentAnalyses.filter(
      (a) =>
        a.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        a.snippet.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [recentAnalyses, searchTerm]);

  const handleOpenAnalysis = (item) => {
    loadChatSession(item.id);
    addToast(`Restored analysis session "${item.title}".`, 'info');
    navigate('/chat');
  };

  return (
    <div className="flex-1 px-margin-mobile md:px-margin-desktop py-10 max-w-content-max-width mx-auto w-full flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Header Section */}
      <header className="mb-10">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 mb-4 text-label-md font-label-md text-muted-text hover:text-coral-accent transition-colors group"
        >
          <span className="material-symbols-outlined text-[20px] transition-transform group-hover:-translate-x-1">
            arrow_back
          </span>
          <span>Back</span>
        </button>
        <h1 className="text-headline-lg font-headline-lg text-on-surface mb-2 font-semibold tracking-tight">
          Recent Analysis
        </h1>
        <p className="text-body-lg font-body-lg text-muted-text">
          Review your past conversations and document deep-dives.
        </p>
      </header>

      {/* Search Bar */}
      <div className="relative w-full mb-10 shadow-[0_4px_24px_rgba(27,28,26,0.08)] rounded-2xl">
        <div className="absolute inset-y-0 left-0 pl-6 flex items-center pointer-events-none text-muted-text">
          <span className="material-symbols-outlined text-[22px]">search</span>
        </div>
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search past analysis..."
          className="block w-full h-search-height pl-14 pr-6 rounded-2xl bg-canvas border border-outline-variant/30 
                     focus:border-coral-accent/60 focus:ring-2 focus:ring-coral-accent/20 
                     text-body-lg font-body-lg text-on-surface placeholder:text-muted-text 
                     transition-all shadow-xs"
        />
        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            className="absolute right-4 top-1/2 -translate-y-1/2 p-2 text-muted-text hover:text-on-surface"
            aria-label="Clear search"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        )}
      </div>

      {/* Analysis List */}
      <div className="space-y-4">
        {filteredAnalyses.length === 0 ? (
          <div className="p-12 text-center text-muted-text bg-card-surface/40 rounded-2xl border border-outline-variant/20">
            <span className="material-symbols-outlined text-[40px] opacity-40 mb-2">history</span>
            <p className="font-headline-md text-lg text-on-surface">No past analyses yet</p>
            <p className="text-sm mt-1">Ask questions in the workspace or chat to generate grounded document analyses.</p>
          </div>
        ) : (
          filteredAnalyses.map((item) => (
            <div
              key={item.id}
              onClick={() => handleOpenAnalysis(item)}
              className="group flex flex-col md:flex-row md:items-center justify-between p-6 rounded-2xl 
                         bg-card-surface/30 hover:bg-card-surface transition-all duration-200 
                         border border-outline-variant/20 hover:border-coral-accent/30 
                         cursor-pointer shadow-xs hover:shadow-sm"
            >
              <div className="flex-grow pr-4">
                <div className="flex items-center gap-3 mb-2">
                  <span className="material-symbols-outlined text-coral-accent text-[22px]">
                    {item.icon || 'description'}
                  </span>
                  <h2 className="text-headline-md font-headline-md text-on-surface group-hover:text-primary transition-colors font-medium text-lg md:text-xl">
                    {item.title}
                  </h2>
                </div>
                <p className="text-body-md font-body-md text-muted-text line-clamp-2 ml-8 text-sm">
                  {item.snippet}
                </p>
              </div>

              <div className="mt-4 md:mt-0 flex items-center gap-6 ml-8 md:ml-0 text-label-sm font-label-sm text-on-surface-variant shrink-0">
                <div className="flex flex-col items-start md:items-end">
                  <span className="opacity-70 uppercase tracking-wider text-[10px] mb-0.5">Date</span>
                  <span className="font-medium text-xs sm:text-sm">{item.date}</span>
                </div>
                <div className="flex flex-col items-start md:items-end">
                  <span className="opacity-70 uppercase tracking-wider text-[10px] mb-0.5">Documents</span>
                  <span className="flex items-center gap-1 font-medium text-xs sm:text-sm">
                    <span className="material-symbols-outlined text-[15px] text-coral-accent">file_copy</span>
                    <span>{item.docCount}</span>
                  </span>
                </div>
                <span className="material-symbols-outlined text-muted-text group-hover:text-coral-accent group-hover:translate-x-1 transition-all text-[20px] hidden sm:block">
                  arrow_forward
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
