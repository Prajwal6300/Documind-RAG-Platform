import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import InitialWorkspace from './pages/InitialWorkspace';
import ChatWorkspace from './pages/ChatWorkspace';
import LibraryPage from './pages/LibraryPage';
import RecentAnalysisPage from './pages/RecentAnalysisPage';
import SettingsPage from './pages/SettingsPage';
import SupportPage from './pages/SupportPage';
import ArchivePage from './pages/ArchivePage';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<InitialWorkspace />} />
        <Route path="/chat" element={<ChatWorkspace />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/recent" element={<RecentAnalysisPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/archive" element={<ArchivePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
