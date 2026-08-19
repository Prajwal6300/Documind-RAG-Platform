import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopNav from './TopNav';
import Toast from '../common/Toast';
import AvatarUploadModal from '../modals/AvatarUploadModal';
import UploadDocumentModal from '../modals/UploadDocumentModal';
import ContactSupportModal from '../modals/ContactSupportModal';

export default function AppLayout() {
  return (
    <div className="flex min-h-screen bg-canvas text-body-text font-body-md antialiased selection:bg-coral-accent selection:text-white">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main App Container */}
      <div className="flex-1 flex flex-col min-w-0 bg-canvas relative min-h-screen overflow-x-hidden">
        {/* Top Navigation */}
        <TopNav />

        {/* Dynamic Route View */}
        <main className="flex-1 flex flex-col">
          <Outlet />
        </main>
      </div>

      {/* Global Modals & Toast Feedback */}
      <AvatarUploadModal />
      <UploadDocumentModal />
      <ContactSupportModal />
      <Toast />
    </div>
  );
}
