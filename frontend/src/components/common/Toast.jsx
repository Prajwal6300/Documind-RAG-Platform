import React from 'react';
import { useApp } from '../../context/AppContext';

export default function Toast() {
  const { toasts, removeToast } = useApp();

  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full">
      {toasts.map((toast) => {
        const isSuccess = toast.type === 'success';
        const isError = toast.type === 'error';
        const isInfo = toast.type === 'info';

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-center justify-between gap-3 px-4 py-3 rounded-xl shadow-lg border transition-all duration-300 transform translate-y-0 ${
              isSuccess
                ? 'bg-surface border-coral-accent/30 text-on-surface'
                : isError
                ? 'bg-error-container text-on-error-container border-error/30'
                : 'bg-card-surface border-outline-variant/40 text-on-surface'
            }`}
          >
            <div className="flex items-center gap-2 text-sm font-label-md">
              <span
                className={`material-symbols-outlined text-[20px] ${
                  isSuccess ? 'text-coral-accent' : isError ? 'text-error' : 'text-primary'
                }`}
              >
                {isSuccess ? 'check_circle' : isError ? 'error' : 'info'}
              </span>
              <span>{toast.message}</span>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-muted-text hover:text-on-surface p-1 rounded-md transition-colors"
              aria-label="Dismiss notification"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
