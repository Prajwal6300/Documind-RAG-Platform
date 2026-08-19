import React from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

export default function Sidebar() {
  const {
    documents,
    userSettings,
    setIsUploadModalOpen,
    mobileSidebarOpen,
    setMobileSidebarOpen,
    addToast
  } = useApp();
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { label: 'New Chat', path: '/', icon: 'add_box' },
    { label: 'Recent Analysis', path: '/recent', icon: 'history' },
    { label: 'Library', path: '/library', icon: 'description' },
    { label: 'Workspace Settings', path: '/settings', icon: 'settings' },
  ];

  const footerItems = [
    { label: 'Support', path: '/support', icon: 'help' },
    { label: 'Archive', path: '/archive', icon: 'archive' },
  ];

  const handleDocClick = (doc) => {
    navigate('/library');
    addToast(`Viewing document "${doc.name}" in Library.`, 'info');
    if (mobileSidebarOpen) setMobileSidebarOpen(false);
  };

  const isNavActive = (path) => {
    if (path === '/') {
      return location.pathname === '/' || location.pathname === '/chat';
    }
    return location.pathname === path;
  };

  const closeSidebar = () => setMobileSidebarOpen(false);

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileSidebarOpen && (
        <div
          onClick={closeSidebar}
          className="fixed inset-0 bg-on-surface/50 z-40 md:hidden backdrop-blur-xs transition-opacity"
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:sticky top-0 left-0 h-screen w-sidebar-width shrink-0 z-50 md:z-30 
                   bg-tertiary-fixed border-r border-outline-variant/20 flex flex-col p-6 
                   transition-transform duration-300 ease-in-out select-none
                   ${mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        {/* Mobile Close Button */}
        <button
          onClick={closeSidebar}
          className="md:hidden absolute top-4 right-4 p-2 text-on-tertiary-fixed hover:text-coral-accent transition-colors"
          aria-label="Close navigation sidebar"
        >
          <span className="material-symbols-outlined text-[24px]">close</span>
        </button>

        {/* Brand Header */}
        <div
          onClick={() => { navigate('/'); closeSidebar(); }}
          className="flex items-center gap-3 mb-6 cursor-pointer group"
        >
          <div className="w-10 h-10 rounded-lg overflow-hidden flex items-center justify-center bg-transparent shrink-0">
            <img
              src="/DocuMind_Logo_4K.png"
              alt="DocuMind Logo"
              className="w-full h-full object-contain group-hover:scale-105 transition-transform"
              onError={(e) => {
                // Fallback to Google hosted logo if local not found
                e.target.src = "https://lh3.googleusercontent.com/aida-public/AB6AXuAuiu6wa71gz2vKPDp45wCy7ewP3vEEQVWK1bJdeKyKQVs5B_IAu0Gc9fP5NNpUX-tM-udr-wtKbLJ1S49rjLE9yCIMIAYjS0N6oiau9RTck46ymwPXXDoPETKVRRvr8ivE90pKmqjrvOp0bl-x4oJRK6gQAAqqygDrQTL67-tjp-inMrHzApNQvbO0qdfWkMRUFN-4iUGqELjbwDxOlFZsPbHx0yfOJGaPjjVxYM5cDFl5V_wvAgIKsYtJSF9aqyyBYok";
              }}
            />
          </div>
          <div>
            <h1 className="font-headline-md text-headline-md text-on-tertiary-fixed font-bold leading-none tracking-tight">
              DocuMind
            </h1>
            <p className="font-label-sm text-label-sm text-on-tertiary-fixed-variant opacity-75 mt-1 uppercase tracking-wider">
              Premium Workspace
            </p>
          </div>
        </div>

        {/* Primary CTA: Upload Documents */}
        <button
          onClick={() => {
            setIsUploadModalOpen(true);
            if (mobileSidebarOpen) setMobileSidebarOpen(false);
          }}
          className="w-full bg-coral-accent text-white font-label-md text-label-md py-3 px-4 rounded-lg 
                     flex items-center justify-center gap-2 mb-6 hover:bg-primary transition-all duration-200 
                     shadow-sm hover:shadow active:scale-[0.99]"
        >
          <span className="material-symbols-outlined text-[20px]">upload_file</span>
          <span>Upload Documents</span>
        </button>

        {/* Main Navigation Links */}
        <nav className="flex-1 flex flex-col gap-1 overflow-y-auto pr-1">
          {navItems.map((item) => {
            const active = isNavActive(item.path);
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={closeSidebar}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg font-label-md text-label-md transition-all duration-150 group ${
                  active
                    ? 'bg-surface-container-highest/70 text-coral-accent font-bold scale-[0.99] shadow-xs'
                    : 'text-on-tertiary-fixed-variant hover:bg-surface-container-highest hover:text-coral-accent'
                }`}
              >
                <span
                  className={`material-symbols-outlined text-[22px] transition-colors ${
                    active ? 'text-coral-accent fill-1' : 'group-hover:text-coral-accent'
                  }`}
                  style={active ? { fontVariationSettings: "'FILL' 1" } : {}}
                >
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          {/* Indexed Documents Section */}
          <div className="mt-6 pt-4 border-t border-outline-variant/20">
            <div className="flex items-center justify-between px-3 mb-2">
              <h2 className="font-label-sm text-label-sm text-muted-text uppercase tracking-wider">
                Indexed Documents
              </h2>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container-highest text-secondary">
                {documents.length}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              {documents.slice(0, 5).map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => handleDocClick(doc)}
                  className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-left text-on-tertiary-fixed-variant 
                             hover:bg-surface-container-highest transition-colors text-sm group w-full"
                >
                  <span className="material-symbols-outlined text-muted-text group-hover:text-coral-accent text-[18px] shrink-0">
                    {doc.icon || 'draft'}
                  </span>
                  <span className="truncate flex-1 font-body-md text-xs group-hover:text-on-surface">
                    {doc.name}
                  </span>
                  {doc.status === 'Processing' && (
                    <span className="material-symbols-outlined text-[14px] text-muted-text animate-spin shrink-0">
                      sync
                    </span>
                  )}
                </button>
              ))}
              {documents.length > 5 && (
                <button
                  onClick={() => { navigate('/library'); closeSidebar(); }}
                  className="text-left px-3 py-1 text-xs text-coral-accent hover:underline font-label-sm mt-1"
                >
                  + {documents.length - 5} more in Library →
                </button>
              )}
            </div>
          </div>
        </nav>

        {/* Footer Navigation */}
        <div className="mt-auto pt-4 border-t border-outline-variant/20 flex flex-col gap-1">
          {footerItems.map((item) => {
            const active = location.pathname === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={closeSidebar}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg font-label-md text-label-md transition-all duration-150 group ${
                  active
                    ? 'bg-surface-container-highest/70 text-coral-accent font-bold'
                    : 'text-on-tertiary-fixed-variant hover:bg-surface-container-highest hover:text-coral-accent'
                }`}
              >
                <span
                  className={`material-symbols-outlined text-[20px] transition-colors ${
                    active ? 'text-coral-accent' : 'group-hover:text-coral-accent'
                  }`}
                  style={active ? { fontVariationSettings: "'FILL' 1" } : {}}
                >
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          {/* User Profile Mini Footer */}
          <div
            onClick={() => { navigate('/settings'); closeSidebar(); }}
            className="flex items-center gap-3 px-3 py-2 mt-2 rounded-lg hover:bg-surface-container-highest cursor-pointer transition-colors group"
          >
            <div className="w-8 h-8 rounded-full overflow-hidden border border-outline-variant shrink-0">
              <img
                src={userSettings.avatarUrl}
                alt={userSettings.name}
                className="w-full h-full object-cover"
                style={{
                  transform: `scale(${userSettings.avatarZoom / 100})`,
                }}
              />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-label-sm font-semibold text-on-tertiary-fixed truncate group-hover:text-coral-accent">
                {userSettings.name}
              </p>
              <p className="text-xs text-muted-text truncate">
                {userSettings.email}
              </p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
