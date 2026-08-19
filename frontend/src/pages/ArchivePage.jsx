import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

export default function ArchivePage() {
  const navigate = useNavigate();
  const { archivedItems, restoreArchivedItem, deleteArchivedItem } = useApp();

  return (
    <div className="flex-1 px-margin-mobile md:px-margin-desktop py-10 max-w-content-max-width mx-auto w-full flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Header Section */}
      <header className="mb-12 border-b border-surface-variant pb-8">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-label-md font-label-md text-muted-text hover:text-primary transition-colors mb-4 group text-sm"
        >
          <span className="material-symbols-outlined text-[20px] transition-transform group-hover:-translate-x-1">
            arrow_back
          </span>
          <span>Back</span>
        </button>
        <h1 className="text-headline-lg font-headline-lg text-on-surface mb-2 font-semibold tracking-tight">
          Archive
        </h1>
        <p className="text-body-lg font-body-lg text-muted-text max-w-2xl">
          Resting documents and past analyses. Items here remain stored but are removed from your primary workspace flow.
        </p>
      </header>

      {/* Ledger Container */}
      <div className="bg-surface-bright rounded-2xl border border-surface-variant/70 shadow-xs overflow-hidden">
        {/* Header */}
        <div className="flex items-center px-6 py-4 bg-surface-container-lowest border-b border-surface-variant/50 text-label-sm font-label-sm text-muted-text uppercase tracking-wider text-xs">
          <div className="w-12 text-center">Type</div>
          <div className="flex-1 pl-4">Title & Context</div>
          <div className="w-32 text-right hidden sm:block">Date Archived</div>
          <div className="w-44 text-right pr-2">Actions</div>
        </div>

        {/* List of Archived Items */}
        <div className="divide-y divide-surface-variant/40">
          {archivedItems.length === 0 ? (
            <div className="p-16 text-center text-muted-text">
              <span className="material-symbols-outlined text-[44px] opacity-30 mb-2">archive</span>
              <p className="font-headline-md text-lg text-on-surface">Archive is empty</p>
              <p className="text-sm mt-1">Archived documents and conversations will appear here.</p>
            </div>
          ) : (
            archivedItems.map((item) => (
              <div
                key={item.id}
                className="flex items-center px-6 py-5 group transition-colors hover:bg-surface-container-lowest/70"
              >
                <div className="w-12 flex justify-center text-muted-text/80">
                  <span className="material-symbols-outlined text-[22px]">
                    {item.icon || 'description'}
                  </span>
                </div>

                <div className="flex-1 pl-4 pr-6 min-w-0">
                  <h2 className="text-body-lg font-headline-md font-medium text-on-surface truncate text-base">
                    {item.title}
                  </h2>
                  <p className="text-label-md font-label-md text-muted-text/90 mt-0.5 truncate text-xs">
                    {item.context}
                  </p>
                </div>

                <div className="w-32 text-right text-label-md text-muted-text hidden sm:block text-xs">
                  {item.dateArchived}
                </div>

                <div className="w-44 flex justify-end items-center gap-3">
                  <button
                    onClick={() => restoreArchivedItem(item.id)}
                    className="text-label-sm font-semibold text-coral-accent hover:text-primary transition-colors flex items-center gap-1 px-2.5 py-1 rounded-md hover:bg-coral-accent/10 cursor-pointer"
                    title="Restore item to active Library"
                  >
                    <span className="material-symbols-outlined text-[16px]">restore</span>
                    <span>Restore</span>
                  </button>
                  <button
                    onClick={() => deleteArchivedItem(item.id)}
                    className="text-label-sm text-error/70 hover:text-error transition-colors p-1.5 rounded-md hover:bg-error-container/20 cursor-pointer"
                    title="Delete permanently"
                    aria-label="Delete permanently"
                  >
                    <span className="material-symbols-outlined text-[18px]">delete_forever</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer hint */}
      <div className="mt-6 text-center">
        <p className="text-label-sm text-muted-text/70 text-xs">
          Showing {archivedItems.length} archived {archivedItems.length === 1 ? 'item' : 'items'}.
        </p>
      </div>
    </div>
  );
}
