import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function SupportPage() {
  const navigate = useNavigate();
  const { setIsSupportModalOpen, addToast } = useApp();
  const [searchQuery, setSearchQuery] = useState('');

  const handleGuideClick = (guideName) => {
    addToast(`Opened "${guideName}" reference documentation.`, 'info');
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
        <div className="grid grid-cols-1 md:grid-cols-12 gap-gutter auto-rows-min">
          {/* Getting Started (Large Card) */}
          <div className="col-span-1 md:col-span-7 bg-card-surface rounded-2xl p-8 md:p-10 transition-all duration-300 hover:-translate-y-0.5 border border-outline-variant/20 hover:border-coral-accent/30 group relative overflow-hidden flex flex-col justify-between shadow-xs">
            <div className="absolute right-0 bottom-0 opacity-5 pointer-events-none transform translate-x-1/4 translate-y-1/4">
              <span className="material-symbols-outlined text-[200px]">rocket_launch</span>
            </div>
            <div className="relative z-10">
              <div className="w-12 h-12 bg-canvas rounded-xl flex items-center justify-center mb-6 text-coral-accent border border-outline-variant/20 shadow-xs">
                <span className="material-symbols-outlined">flag</span>
              </div>
              <h2 className="text-headline-lg font-headline-lg text-on-surface mb-3 font-semibold">
                Getting Started
              </h2>
              <p className="text-body-md font-body-md text-muted-text mb-8 max-w-md">
                Lay the foundation. Learn how to construct your premium workspace, index your first documents, and initiate semantic analysis.
              </p>
            </div>
            <button
              onClick={() => handleGuideClick('Quickstart Guide')}
              className="inline-flex items-center gap-2 text-coral-accent font-label-md text-sm font-semibold hover:text-primary transition-colors cursor-pointer w-fit"
            >
              <span>Read the Quickstart Guide</span>
              <span className="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">
                arrow_forward
              </span>
            </button>
          </div>

          {/* Search Tips (Tall Card) */}
          <div className="col-span-1 md:col-span-5 bg-card-surface rounded-2xl p-8 md:p-10 transition-all duration-300 hover:-translate-y-0.5 border border-outline-variant/20 hover:border-coral-accent/30 group relative overflow-hidden flex flex-col justify-between shadow-xs">
            <div>
              <div className="w-12 h-12 bg-canvas rounded-xl flex items-center justify-center mb-6 text-coral-accent border border-outline-variant/20 shadow-xs">
                <span className="material-symbols-outlined">manage_search</span>
              </div>
              <h2 className="text-headline-md font-headline-md text-on-surface mb-3 font-semibold">
                Advanced Search Tips
              </h2>
              <ul className="text-body-md font-body-md text-muted-text space-y-3 mb-6 text-sm">
                <li className="flex items-start gap-2.5">
                  <span className="material-symbols-outlined text-[18px] text-coral-accent mt-0.5 shrink-0">check_circle</span>
                  <span>Utilize boolean operators for precision.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="material-symbols-outlined text-[18px] text-coral-accent mt-0.5 shrink-0">check_circle</span>
                  <span>Filter by document metadata and source dates.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="material-symbols-outlined text-[18px] text-coral-accent mt-0.5 shrink-0">check_circle</span>
                  <span>Leverage semantic clustering for abstract concepts.</span>
                </li>
              </ul>
            </div>
            <button
              onClick={() => handleGuideClick('Search Queries Masterclass')}
              className="inline-flex items-center gap-2 text-coral-accent font-label-md text-sm font-semibold hover:text-primary transition-colors cursor-pointer w-fit"
            >
              <span>Master Search Queries</span>
              <span className="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">
                arrow_forward
              </span>
            </button>
          </div>

          {/* Managing Documents (Wide Card) */}
          <div className="col-span-1 md:col-span-12 bg-card-surface rounded-2xl p-8 md:p-10 transition-all duration-300 hover:-translate-y-0.5 border-t-4 border-coral-accent/80 border border-outline-variant/20 group flex flex-col md:flex-row gap-8 items-start md:items-center justify-between shadow-xs">
            <div className="max-w-2xl">
              <div className="flex items-center gap-3.5 mb-3">
                <div className="w-10 h-10 bg-canvas rounded-xl flex items-center justify-center text-coral-accent border border-outline-variant/20 shadow-xs">
                  <span className="material-symbols-outlined">folder_managed</span>
                </div>
                <h2 className="text-headline-md font-headline-md text-on-surface font-semibold">
                  Managing Documents
                </h2>
              </div>
              <p className="text-body-md font-body-md text-muted-text text-sm md:text-base">
                Organize your academic or professional library. Discover best practices for archiving, tagging, and maintaining a high-signal repository for the AI to query.
              </p>
            </div>
            <button
              onClick={() => handleGuideClick('Library Protocols')}
              className="shrink-0 inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-outline-variant text-on-surface-variant text-label-md text-sm font-medium hover:bg-canvas hover:text-coral-accent hover:border-coral-accent/40 transition-all cursor-pointer"
            >
              <span>View Library Protocols</span>
            </button>
          </div>
        </div>
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
