import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { api } from '../../api/client';

export default function TopNav({ showBackButton = true }) {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    documents,
    userSettings,
    setMobileSidebarOpen,
    addToast
  } = useApp();

  const [health, setHealth] = useState(null);
  const [healthChecking, setHealthChecking] = useState(false);

  const checkHealth = async () => {
    setHealthChecking(true);
    try {
      const data = await api.getHealth();
      setHealth(data);
      addToast(
        `Gemini: ${data?.gemini?.ready ? 'Ready' : 'Not ready'} · Database: ${data?.database?.status === 'ok' ? 'Connected' : 'Unavailable'} · Status: ${data?.status}`,
        'info'
      );
    } catch (err) {
      setHealth(null);
      addToast(`Health check failed: ${err.message}`, 'error');
    } finally {
      setHealthChecking(false);
    }
  };

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  const isBackendOk = health?.status === 'healthy' || health?.status === 'degraded';
  const geminiReady = health?.gemini?.ready === true;

  const handleBack = () => {
    if (window.history.length > 1 && location.pathname !== '/') {
      navigate(-1);
    } else {
      navigate('/');
    }
  };

  return (
    <header className="sticky top-0 z-30 flex justify-between items-center w-full px-margin-mobile md:px-margin-desktop h-16 bg-background/90 backdrop-blur-sm border-b border-outline-variant/10">
      {/* Left side: Mobile Menu + Back Button */}
      <div className="flex items-center gap-3">
        {/* Mobile menu trigger */}
        <button
          onClick={() => setMobileSidebarOpen(true)}
          className="md:hidden p-2 -ml-2 text-on-surface-variant hover:text-coral-accent rounded-lg transition-colors"
          aria-label="Open sidebar menu"
        >
          <span className="material-symbols-outlined text-[24px]">menu</span>
        </button>

        {/* Back Button */}
        {showBackButton && location.pathname !== '/' && (
          <button
            onClick={handleBack}
            className="flex items-center gap-1.5 text-on-surface-variant hover:text-coral-accent transition-colors group px-2 py-1.5 rounded-lg hover:bg-surface-container"
            aria-label="Go back to previous page"
          >
            <span className="material-symbols-outlined text-[20px] transition-transform group-hover:-translate-x-0.5">
              arrow_back
            </span>
            <span className="font-label-md text-label-md">Back</span>
          </button>
        )}

        {/* Mobile Brand / Page Indicator */}
        <div className="md:hidden flex items-center gap-2">
          <img
            src="/DocuMind_Logo_4K.png"
            alt="DocuMind"
            className="w-7 h-7 object-contain"
            onError={(e) => {
              e.target.src = "https://lh3.googleusercontent.com/aida-public/AB6AXuAuiu6wa71gz2vKPDp45wCy7ewP3vEEQVWK1bJdeKyKQVs5B_IAu0Gc9fP5NNpUX-tM-udr-wtKbLJ1S49rjLE9yCIMIAYjS0N6oiau9RTck46ymwPXXDoPETKVRRvr8ivE90pKmqjrvOp0bl-x4oJRK6gQAAqqygDrQTL67-tjp-inMrHzApNQvbO0qdfWkMRUFN-4iUGqELjbwDxOlFZsPbHx0yfOJGaPjjVxYM5cDFl5V_wvAgIKsYtJSF9aqyyBYok";
            }}
          />
          <span className="font-headline-md text-lg font-bold text-on-surface">DocuMind</span>
        </div>
      </div>

      {/* Right side: Status, Index count, Avatar */}
      <div className="flex items-center gap-4 sm:gap-6">
        {/* Gemini Active Status Pill */}
        <button
          onClick={checkHealth}
          disabled={healthChecking}
          className="flex items-center gap-2 px-2.5 py-1 rounded-full hover:bg-surface-container transition-colors cursor-pointer text-xs sm:text-sm font-label-md disabled:opacity-60"
          title="Click to check model telemetry"
        >
          <span
            className={`w-2 h-2 rounded-full ${
              healthChecking ? 'bg-amber-400 animate-pulse'
              : isBackendOk
                ? geminiReady ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'
                : 'bg-red-500'
            }`}
          />
          <span className="text-on-surface-variant font-medium hover:text-coral-accent transition-colors">
            {healthChecking
              ? 'Checking...'
              : isBackendOk
                ? geminiReady ? 'Gemini · Ready' : 'Gemini · Degraded'
                : 'Server · Unreachable'}
          </span>
        </button>

        {/* Files Indexed Counter */}
        <button
          onClick={() => navigate('/library')}
          className="hidden sm:flex items-center gap-1.5 text-on-surface-variant hover:text-coral-accent font-body-md text-sm transition-colors cursor-pointer py-1 px-2 rounded-lg hover:bg-surface-container"
          title="View all files in Library"
        >
          <span className="material-symbols-outlined text-[18px]">folder_open</span>
          <span>{documents.length} Files Indexed</span>
        </button>

        {/* Profile Avatar Button (Navigates to Settings) */}
        <button
          onClick={() => navigate('/settings')}
          className="w-9 h-9 rounded-full border border-outline-variant/40 overflow-hidden 
                     flex items-center justify-center hover:border-coral-accent 
                     hover:ring-2 hover:ring-coral-accent/20 transition-all cursor-pointer"
          title="Account & Settings"
          aria-label="View account settings"
        >
          <img
            src={userSettings.avatarUrl}
            alt={userSettings.name}
            className="w-full h-full object-cover"
            style={{
              transform: `scale(${userSettings.avatarZoom / 100})`,
            }}
          />
        </button>
      </div>
    </header>
  );
}
