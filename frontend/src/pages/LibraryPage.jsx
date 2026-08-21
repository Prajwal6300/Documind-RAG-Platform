import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { api } from '../api/client';

export default function LibraryPage() {
  const navigate = useNavigate();
  const { documents, isLoadingDocs, deleteDocument, setIsUploadModalOpen, addToast, serverError, retryConnection } = useApp();

  const [selectedType, setSelectedType] = useState('All Types');
  const [sortBy, setSortBy] = useState('date'); // 'date' | 'name' | 'pages'
  const [searchFilter, setSearchFilter] = useState('');
  const [isFilterDropdownOpen, setIsFilterDropdownOpen] = useState(false);
  const [isSortDropdownOpen, setIsSortDropdownOpen] = useState(false);

  const filterRef = useRef(null);
  const sortRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (filterRef.current && !filterRef.current.contains(e.target)) {
        setIsFilterDropdownOpen(false);
      }
      if (sortRef.current && !sortRef.current.contains(e.target)) {
        setIsSortDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredAndSortedDocs = useMemo(() => {
    return documents
      .filter((doc) => {
        const matchesType =
          selectedType === 'All Types' ||
          doc.type?.toUpperCase() === selectedType.toUpperCase();
        const matchesSearch =
          !searchFilter.trim() ||
          doc.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
          doc.title?.toLowerCase().includes(searchFilter.toLowerCase()) ||
          doc.documentSummary?.toLowerCase().includes(searchFilter.toLowerCase()) ||
          doc.documentType?.toLowerCase().includes(searchFilter.toLowerCase());
        return matchesType && matchesSearch;
      })
      .sort((a, b) => {
        if (sortBy === 'name') {
          return a.name.localeCompare(b.name);
        }
        if (sortBy === 'pages') {
          return (b.pages || 0) - (a.pages || 0);
        }
        // Default to order in list (date added)
        return 0;
      });
  }, [documents, selectedType, sortBy, searchFilter]);

  const handleView = (doc) => {
    const analyzed = doc.analysisStatus === 'analyzed' && doc.documentSummary
      ? `${doc.documentType || 'document'}: ${doc.documentSummary}`
      : doc.warning || `Analysis status: ${doc.analysisStatus || 'pending'}`;
    addToast(`"${doc.name}" ${analyzed}`, 'info');
  };

  const handleDownload = (doc) => {
    const url = api.getDownloadUrl(doc.id);
    window.open(url, '_blank');
    addToast(`Downloading "${doc.name}"...`, 'info');
  };

  return (
    <div className="flex-1 px-margin-mobile md:px-margin-desktop py-8 md:py-10 max-w-content-max-width mx-auto w-full flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Header & Action Controls */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8 shrink-0">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1 text-muted-text hover:text-coral-accent transition-colors font-label-md text-label-md mb-3 group"
          >
            <span className="material-symbols-outlined text-[20px] transition-transform group-hover:-translate-x-1">
              arrow_back
            </span>
            <span>Back</span>
          </button>
          <h1 className="text-display-lg font-display-lg text-on-surface mb-2 font-semibold tracking-tight">
            Library
          </h1>
          <p className="text-body-lg font-body-lg text-muted-text max-w-2xl">
            Manage and organize your indexed documents. <strong className="text-on-surface font-semibold">{documents.length} files</strong> currently available for AI analysis.
          </p>
        </div>

        {/* Filter & Sort Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Quick Search */}
          <div className="relative">
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search library..."
              className="h-10 pl-9 pr-3 text-xs bg-card-surface border border-muted-text/20 rounded-lg text-on-surface focus:outline-none focus:border-coral-accent"
            />
            <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-text text-[16px]">
              search
            </span>
          </div>

          {/* Filter Dropdown */}
          <div className="relative" ref={filterRef}>
            <button
              onClick={() => setIsFilterDropdownOpen(!isFilterDropdownOpen)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-muted-text/20 bg-card-surface text-body-text font-label-md text-xs sm:text-sm hover:bg-surface-container-highest transition-colors cursor-pointer"
              aria-expanded={isFilterDropdownOpen}
            >
              <span className="material-symbols-outlined text-[18px]">filter_list</span>
              <span>{selectedType}</span>
              <span className="material-symbols-outlined text-[18px] ml-1">expand_more</span>
            </button>

            {isFilterDropdownOpen && (
              <div className="absolute top-full right-0 mt-2 w-44 bg-card-surface border border-muted-text/20 rounded-xl shadow-xl py-1.5 z-50 animate-in fade-in">
                {['All Types', 'PDF', 'DOCX', 'XLSX', 'TXT', 'CSV', 'PPTX'].map((type) => (
                  <button
                    key={type}
                    onClick={() => { setSelectedType(type); setIsFilterDropdownOpen(false); }}
                    className="w-full flex items-center justify-between px-4 py-2 text-xs font-label-md text-on-surface hover:bg-surface-container transition-colors"
                  >
                    <span>{type}</span>
                    {selectedType === type && (
                      <span className="material-symbols-outlined text-[16px] text-coral-accent">check</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Sort Dropdown */}
          <div className="relative" ref={sortRef}>
            <button
              onClick={() => setIsSortDropdownOpen(!isSortDropdownOpen)}
              className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-muted-text/20 bg-card-surface text-body-text font-label-md text-xs sm:text-sm hover:bg-surface-container-highest transition-colors cursor-pointer"
              aria-expanded={isSortDropdownOpen}
            >
              <span className="material-symbols-outlined text-[18px]">sort</span>
              <span>
                {sortBy === 'name' ? 'Name (A-Z)' : sortBy === 'pages' ? 'Page Count' : 'Date Added'}
              </span>
              <span className="material-symbols-outlined text-[18px] ml-1">expand_more</span>
            </button>

            {isSortDropdownOpen && (
              <div className="absolute top-full right-0 mt-2 w-44 bg-card-surface border border-muted-text/20 rounded-xl shadow-xl py-1.5 z-50 animate-in fade-in">
                {[
                  { key: 'date', label: 'Date Added' },
                  { key: 'name', label: 'Name (A-Z)' },
                  { key: 'pages', label: 'Page Count' }
                ].map((item) => (
                  <button
                    key={item.key}
                    onClick={() => { setSortBy(item.key); setIsSortDropdownOpen(false); }}
                    className="w-full flex items-center justify-between px-4 py-2 text-xs font-label-md text-on-surface hover:bg-surface-container transition-colors"
                  >
                    <span>{item.label}</span>
                    {sortBy === item.key && (
                      <span className="material-symbols-outlined text-[16px] text-coral-accent">check</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Upload Button */}
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-coral-accent text-white font-label-md text-xs sm:text-sm hover:bg-primary transition-colors shadow-xs cursor-pointer"
          >
            <span className="material-symbols-outlined text-[18px]">upload</span>
            <span>Upload</span>
          </button>
        </div>
      </header>

      {/* Document Table Area */}
      <div className="flex-1 overflow-auto border border-muted-text/15 rounded-2xl bg-canvas shadow-xs relative">
        {/* Table Header (Sticky) */}
        <div className="sticky top-0 bg-card-surface z-10 grid grid-cols-[1fr_80px_120px_110px_90px] sm:grid-cols-[1fr_90px_130px_120px_100px] gap-4 p-4 border-b border-muted-text/15 items-center select-none text-xs">
          <div className="font-label-sm text-muted-text uppercase tracking-widest pl-2">Name</div>
          <div className="font-label-sm text-muted-text uppercase tracking-widest text-center">Type</div>
          <div className="font-label-sm text-muted-text uppercase tracking-widest text-center hidden sm:block">Date Added</div>
          <div className="font-label-sm text-muted-text uppercase tracking-widest text-center">Status</div>
          <div className="font-label-sm text-muted-text uppercase tracking-widest text-right pr-2">Actions</div>
        </div>

        {/* Table Body */}
        <div className="divide-y divide-muted-text/10">
          {isLoadingDocs ? (
            <div className="py-16 text-center text-muted-text">
              <span className="material-symbols-outlined text-[36px] animate-spin inline-block mb-2 opacity-40">progress_activity</span>
              <p className="text-sm">Loading documents...</p>
            </div>
          ) : serverError ? (
            <div className="py-16 text-center text-muted-text">
              <span className="material-symbols-outlined text-[40px] opacity-40 mb-2">cloud_off</span>
              <p className="font-headline-md text-lg text-on-surface">Cannot load your library</p>
              <p className="text-sm mt-1">{serverError}</p>
              <button
                onClick={retryConnection}
                className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-coral-accent text-white text-xs font-label-md hover:bg-primary transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px]">refresh</span>
                Retry connection
              </button>
            </div>
          ) : filteredAndSortedDocs.length === 0 ? (
            <div className="py-16 text-center text-muted-text">
              <span className="material-symbols-outlined text-[40px] opacity-40 mb-2">folder_off</span>
              <p className="font-headline-md text-lg text-on-surface">No documents found</p>
              <p className="text-sm mt-1">Upload a PDF, DOCX, XLSX, or TXT file to start indexing.</p>
              <button
                onClick={() => setIsUploadModalOpen(true)}
                className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-coral-accent text-white text-xs font-label-md hover:bg-primary transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px]">upload_file</span>
                <span>Upload Document</span>
              </button>
            </div>
          ) : (
            filteredAndSortedDocs.map((doc) => {
              const isProcessing = doc.status === 'Processing' || doc.status === 'Uploading';
              const isFailed = doc.status === 'Failed';
              return (
                <div
                  key={doc.id}
                  className={`grid grid-cols-[1fr_80px_120px_110px_90px] sm:grid-cols-[1fr_90px_130px_120px_100px] gap-4 p-4 items-center hover:bg-surface-container-lowest/70 transition-colors group ${
                    isProcessing ? 'opacity-80 bg-surface-container-low/40' : isFailed ? 'bg-error-container/10' : ''
                  }`}
                >
                  {/* Name & metadata */}
                  <div className="flex items-center gap-3 pl-2 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center shrink-0 border border-outline-variant/30">
                      <span className={`material-symbols-outlined text-[22px] ${doc.accentColor || 'text-coral-accent'}`}>
                        {doc.icon || 'description'}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h2 className="text-headline-md font-headline-md text-on-surface truncate text-base leading-tight font-medium">
                          {doc.title || doc.name}
                        </h2>
                        {doc.documentType && doc.analysisStatus === 'analyzed' && (
                          <span
                            className="inline-flex items-center px-1.5 py-0.5 rounded bg-secondary/10 text-secondary border border-secondary/20 text-[10px] font-medium shrink-0 capitalize"
                            title={doc.documentSummary || doc.documentType}
                          >
                            {doc.documentType.replaceAll('_', ' ')}
                          </span>
                        )}
                        {doc.is_low_text && (
                          <span
                            className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 border border-amber-500/30 text-[10px] font-medium shrink-0"
                            title={doc.warning || "This document appears to contain very little extractable text — answers may be limited."}
                          >
                            <span className="material-symbols-outlined text-[12px]">warning</span>
                            <span>Low Text</span>
                          </span>
                        )}
                      </div>
                      <p className="text-label-sm font-label-sm text-muted-text mt-0.5 truncate text-xs">
                        {doc.documentSummary || `${doc.size} • ${doc.pages} ${doc.pages === 1 ? 'Page' : 'Pages'} • ${doc.chunks} ${doc.chunks === 1 ? 'Chunk' : 'Chunks'}`}
                      </p>
                      <p className="text-[11px] text-muted-text/80 mt-0.5 truncate">
                        {doc.size} • {doc.pages} {doc.pages === 1 ? 'Page' : 'Pages'} • {doc.chunks} {doc.chunks === 1 ? 'Chunk' : 'Chunks'}
                      </p>
                    </div>
                  </div>

                  {/* Type Pill */}
                  <div className="flex justify-center">
                    <span className="px-2 py-0.5 rounded bg-surface-container-high text-body-text font-label-sm text-[11px] font-semibold tracking-wider">
                      {doc.type}
                    </span>
                  </div>

                  {/* Date Added */}
                  <div className="text-center text-body-md text-muted-text text-xs hidden sm:block">
                    {doc.dateAdded}
                  </div>

                  {/* Status Indicator */}
                  <div className="flex justify-center items-center gap-1.5">
                    {isProcessing ? (
                      <div className="flex items-center gap-1 text-muted-text text-xs font-semibold">
                        <span className="material-symbols-outlined text-[16px] animate-spin text-coral-accent">
                          sync
                        </span>
                        <span className="uppercase tracking-wider text-[10px]">Processing</span>
                      </div>
                    ) : isFailed ? (
                      <div className="flex items-center gap-1 text-error text-xs font-semibold" title={doc.errorMessage || 'Parsing failed'}>
                        <span className="material-symbols-outlined text-[16px] text-error">
                          error
                        </span>
                        <span className="uppercase tracking-wider text-[10px]">Failed</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-primary text-xs font-semibold">
                        <span className="material-symbols-outlined text-[16px] text-emerald-600">
                          check_circle
                        </span>
                        <span className="uppercase tracking-wider text-[10px]">Indexed</span>
                      </div>
                    )}
                  </div>

                  {/* Row Actions */}
                  <div className="flex justify-end gap-1.5 pr-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => handleView(doc)}
                      className="p-1.5 text-muted-text hover:text-coral-accent hover:bg-surface-container rounded-lg transition-colors cursor-pointer"
                      title="Inspect document info"
                      aria-label={`View ${doc.name}`}
                    >
                      <span className="material-symbols-outlined text-[18px]">visibility</span>
                    </button>
                    <button
                      onClick={() => handleDownload(doc)}
                      className="p-1.5 text-muted-text hover:text-coral-accent hover:bg-surface-container rounded-lg transition-colors cursor-pointer"
                      title="Download file"
                      aria-label={`Download ${doc.name}`}
                    >
                      <span className="material-symbols-outlined text-[18px]">download</span>
                    </button>
                    <button
                      onClick={() => deleteDocument(doc.id)}
                      className="p-1.5 text-muted-text hover:text-error hover:bg-error-container/20 rounded-lg transition-colors cursor-pointer"
                      title="Move to Archive"
                      aria-label={`Archive ${doc.name}`}
                    >
                      <span className="material-symbols-outlined text-[18px]">archive</span>
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-4 flex justify-between items-center text-xs text-muted-text shrink-0">
        <span>
          Showing {filteredAndSortedDocs.length} of {documents.length} documents
        </span>
        <span className="hidden sm:inline font-label-sm">
          Strictly grounded local RAG corpus with Gemini
        </span>
      </div>
    </div>
  );
}
