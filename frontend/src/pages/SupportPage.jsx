import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function SupportPage() {
  const navigate = useNavigate();
  const { setIsSupportModalOpen, addToast, supportGuides, isLoadingSupportGuides, serverError, retryConnection } = useApp();
  const [searchQuery, setSearchQuery] = useState('');

  const filteredGuides = supportGuides.filter((guide) => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return true;
    return (
      guide.title.toLowerCase().includes(q) ||
      guide.summary.toLowerCase().includes(q) ||
      guide.category.toLowerCase().includes(q)
    );
  });

  const handleGuideClick = (guide) => {
    addToast(`Guide loaded from backend: "${guide.title}".`, 'info');
  };

  return (
    <div className="flex-1 px-margin-mobile md:px-margin-desktop py-10 md:py-16 max-w-content-max-width mx-auto w-full flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Back Button */}
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-muted-text hover:text-coral-accent transition-colors mb-6 group font-label-md text-sm"
      >
        <span className="material-symbols-outlined text-[20px] group-hover:-translate-x-1 transition-transform">
          arrow_back
        </span>
        <span>Back</span>
      </button>

      {/* Page Header */}
      <header className="mb-14 text-center md:text-left max-w-3xl">
        <h1 className="text-display-lg font-display-lg text-on-surface mb-4 font-semibold tracking-tight">
          How can we assist you today?
        </h1>
        <p className="text-body-lg font-body-lg text-muted-text leading-relaxed">
          Explore our curated guides to maximize your scholarly research and streamline your document analysis within the DocuMind workspace.
        </p>

        {/* Premium Search Bar */}
        <div className="mt-8 relative max-w-2xl">
          <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none text-muted-text">
            <span className="material-symbols-outlined text-[22px]">search</span>
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search guides, tutorials, or FAQs..."
            className="w-full h-search-height bg-canvas border border-outline-variant/30 text-on-surface rounded-2xl pl-14 pr-6 
                       focus:ring-2 focus:ring-coral-accent/20 focus:border-coral-accent text-body-lg placeholder:text-muted-text/70 
                       transition-all shadow-[0_4px_20px_rgba(27,28,26,0.04)]"
          />
        </div>
      </header>

      {/* Featured Bento Grid */}
      <section className="mb-16">
        {isLoadingSupportGuides ? (
          <div className="p-12 text-center text-muted-text bg-card-surface/40 rounded-2xl border border-outline-variant/20">
            <span className="material-symbols-outlined text-[36px] animate-spin inline-block mb-2 opacity-40">progress_activity</span>
            <p className="text-sm">Loading support guides...</p>
          </div>
        ) : serverError ? (
          <div className="p-12 text-center text-muted-text bg-card-surface/40 rounded-2xl border border-outline-variant/20">
            <span className="material-symbols-outlined text-[40px] opacity-40 mb-2">cloud_off</span>
            <p className="font-headline-md text-lg text-on-surface">Cannot load support guides</p>
            <p className="text-sm mt-1">{serverError}</p>
            <button
              onClick={retryConnection}
              className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-coral-accent text-white text-xs font-label-md hover:bg-primary transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-[16px]">refresh</span>
              Retry connection
            </button>
          </div>
        ) : filteredGuides.length === 0 ? (
          <div className="p-12 text-center text-muted-text bg-card-surface/40 rounded-2xl border border-outline-variant/20">
            <span className="material-symbols-outlined text-[40px] opacity-40 mb-2">help</span>
            <p className="font-headline-md text-lg text-on-surface">No matching guides</p>
            <p className="text-sm mt-1">The backend returned no support guide records for this search.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-12 gap-gutter auto-rows-min">
            {filteredGuides.map((guide, index) => (
              <div
                key={guide.id}
                className={`${index === 0 ? 'md:col-span-7' : index === 1 ? 'md:col-span-5' : 'md:col-span-12'} col-span-1 bg-card-surface rounded-2xl p-8 md:p-10 transition-all duration-300 hover:-translate-y-0.5 border border-outline-variant/20 hover:border-coral-accent/30 group relative overflow-hidden flex flex-col justify-between shadow-xs`}
              >
                <div>
                  <div className="w-12 h-12 bg-canvas rounded-xl flex items-center justify-center mb-6 text-coral-accent border border-outline-variant/20 shadow-xs">
                    <span className="material-symbols-outlined">{guide.icon || 'article'}</span>
                  </div>
                  <p className="text-label-sm text-muted-text uppercase tracking-wider mb-2">{guide.category}</p>
                  <h2 className="text-headline-md font-headline-md text-on-surface mb-3 font-semibold">
                    {guide.title}
                  </h2>
                  <p className="text-body-md font-body-md text-muted-text mb-8 max-w-2xl text-sm md:text-base">
                    {guide.summary}
                  </p>
                </div>
                <button
                  onClick={() => handleGuideClick(guide)}
                  className="inline-flex items-center gap-2 text-coral-accent font-label-md text-sm font-semibold hover:text-primary transition-colors cursor-pointer w-fit"
                >
                  <span>View Guide Record</span>
                  <span className="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">
                    arrow_forward
                  </span>
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Contact Support Section */}
      <section className="max-w-3xl mx-auto text-center py-10 border-t border-outline-variant/20 w-full">
        <span className="material-symbols-outlined text-[48px] text-muted-text mb-4 opacity-40">
          forum
        </span>
        <h3 className="text-headline-md font-headline-md text-on-surface mb-2 font-semibold">
          Still need assistance?
        </h3>
        <p className="text-body-md font-body-md text-muted-text mb-6 max-w-lg mx-auto text-sm">
          Our technical specialists are available to resolve complex issues or discuss bespoke integration requirements for your workspace.
        </p>
        <button
          onClick={() => setIsSupportModalOpen(true)}
          className="bg-coral-accent hover:bg-primary transition-colors text-white text-label-md font-medium rounded-xl px-8 py-3.5 inline-flex items-center gap-2 shadow-sm hover:shadow active:scale-95 cursor-pointer"
        >
          <span className="material-symbols-outlined text-[20px]">mail</span>
          <span>Contact Support</span>
        </button>
      </section>
    </div>
  );
}
