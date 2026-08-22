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
    recentlyUploadedDocId,
    addToast
  } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const navScrollRef = React.useRef(null);

  // Show both indexed and processing/uploading documents in active sidebar list
  const activeDocs = documents.filter((doc) => doc.status === 'Indexed' || doc.status === 'Processing' || doc.status === 'Uploading');

  // Auto-scroll sidebar navigation to top when a new document is uploaded
  React.useEffect(() => {
    if (recentlyUploadedDocId && navScrollRef.current) {
      navScrollRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [recentlyUploadedDocId]);

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
                e.currentTarget.style.display = 'none';
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
                     shadow-sm hover:shadow active:scale-[0.99] cursor-pointer"
        >
          <span className="material-symbols-outlined text-[20px]">upload_file</span>
          <span>Upload Documents</span>
        </button>

        {/* Main Navigation Links */}
        <nav ref={navScrollRef} className="flex-1 flex flex-col gap-1 overflow-y-auto pr-1">
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
                {activeDocs.length}
              </span>
            </div>
            <div className="flex flex-col gap-1">
              {activeDocs.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-text italic">No documents indexed yet.</p>
              ) : (
                activeDocs.slice(0, 6).map((doc) => {
                  const isNew = doc.id === recentlyUploadedDocId;
                  const isProcessing = doc.status === 'Processing' || doc.status === 'Uploading';
                  return (
                    <button
                      key={doc.id}
                      onClick={() => handleDocClick(doc)}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all duration-300 text-sm group w-full ${
                        isNew
                          ? 'bg-coral-accent/15 border border-coral-accent/40 text-coral-accent shadow-xs animate-in fade-in zoom-in-95'
                          : 'text-on-tertiary-fixed-variant hover:bg-surface-container-highest'
                      }`}
                    >
                      <span className={`material-symbols-outlined text-[18px] shrink-0 ${
                        isNew ? 'text-coral-accent' : 'text-muted-text group-hover:text-coral-accent'
                      }`}>
                        {doc.icon || 'description'}
                      </span>
                      <span className="truncate flex-1 font-body-md text-xs group-hover:text-on-surface">
                        {doc.title || doc.name}
                      </span>
                      {isProcessing ? (
                        <span className="inline-flex items-center gap-1 text-[10px] text-amber-500 font-semibold px-1.5 py-0.5 rounded bg-amber-500/10 shrink-0">
                          <span className="material-symbols-outlined text-[12px] animate-spin">sync</span>
                          <span>Indexing</span>
                        </span>
                      ) : isNew ? (
                        <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-coral-accent text-white shrink-0 tracking-wide uppercase">
                          New
                        </span>
                      ) : null}
                    </button>
                  );
                })
              )}
              {activeDocs.length > 6 && (
                <button
                  onClick={() => { navigate('/library'); closeSidebar(); }}
                  className="text-left px-3 py-1 text-xs text-coral-accent hover:underline font-label-sm mt-1 cursor-pointer"
                >
                  + {activeDocs.length - 6} more in Library →
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
                src={userSettings.avatarUrl || '/DocuMind_Logo_4K.png'}
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
