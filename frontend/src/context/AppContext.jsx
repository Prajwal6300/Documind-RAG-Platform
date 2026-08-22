import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const AppContext = createContext();

export function AppProvider({ children }) {
  // Real Backend State (Zero Mock Data)
  const [documents, setDocuments] = useState([]);
  const [archivedItems, setArchivedItems] = useState([]);
  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const [supportGuides, setSupportGuides] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [selectedScope, setSelectedScope] = useState('All Documents');

  const [isAiThinking, setIsAiThinking] = useState(false);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [isLoadingArchive, setIsLoadingArchive] = useState(true);
  const [isLoadingRecent, setIsLoadingRecent] = useState(true);
  const [isLoadingSettings, setIsLoadingSettings] = useState(true);
  const [isLoadingSupportGuides, setIsLoadingSupportGuides] = useState(true);
  const [recentlyUploadedDocId, setRecentlyUploadedDocId] = useState(null);

  // True when the backend is unreachable so pages can show a clear
  // "can't connect to server" state instead of a silent failure.
  const [serverError, setServerError] = useState(null);

  // User Profile & Settings State
  const [userSettings, setUserSettings] = useState({
    name: "Local Workspace",
    email: "",
    role: "Workspace User",
    avatarUrl: "",
    avatarZoom: 110,
    avatarPos: { x: 0, y: 0 },
    plan: "Self-hosted",
    nextBilling: "Not applicable",
    notifications: {
      documentSummaries: true,
      productUpdates: false,
    },
    privacy: {
      aiTraining: false,
    }
  });

  // Modal States
  const [isAvatarModalOpen, setIsAvatarModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isSupportModalOpen, setIsSupportModalOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Toast Notification System
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      removeToast(id);
    }, 4000);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // -------------------------------------------------------------------------
  // Fetch Real Data from Backend
  // -------------------------------------------------------------------------

  const fetchDocuments = useCallback(async () => {
    setIsLoadingDocs(true);
    try {
      const data = await api.getDocuments();
      setDocuments(data);
      setServerError(null);
    } catch (err) {
      setServerError(err.message);
      addToast(`Couldn't load documents: ${err.message}`, 'error');
    } finally {
      setIsLoadingDocs(false);
    }
  }, [addToast]);

  const fetchRecentAnalyses = useCallback(async () => {
    setIsLoadingRecent(true);
    try {
      const data = await api.getChatSessions();
      setRecentAnalyses(data);
      setServerError(null);
    } catch (err) {
      setServerError(err.message);
      addToast(`Couldn't load chat history: ${err.message}`, 'error');
    } finally {
      setIsLoadingRecent(false);
    }
  }, [addToast]);

  const fetchArchive = useCallback(async () => {
    setIsLoadingArchive(true);
    try {
      const data = await api.getArchive();
      setArchivedItems(data);
      setServerError(null);
    } catch (err) {
      setServerError(err.message);
      addToast(`Couldn't load archive: ${err.message}`, 'error');
    } finally {
      setIsLoadingArchive(false);
    }
  }, [addToast]);

  const fetchSuggestedQuestions = useCallback(async () => {
    try {
      const data = await api.getSuggestedQuestions();
      setSuggestedQuestions(data);
    } catch (err) {
      addToast(`Couldn't load suggested questions: ${err.message}`, 'error');
    }
  }, [addToast]);

  const fetchSettings = useCallback(async () => {
    setIsLoadingSettings(true);
    try {
      const data = await api.getSettings();
      setUserSettings(data);
      setServerError(null);
    } catch (err) {
      setServerError(err.message);
      addToast(`Couldn't load settings: ${err.message}`, 'error');
    } finally {
      setIsLoadingSettings(false);
    }
  }, [addToast]);

  const fetchSupportGuides = useCallback(async () => {
    setIsLoadingSupportGuides(true);
    try {
      const data = await api.getSupportGuides();
      setSupportGuides(data);
      setServerError(null);
    } catch (err) {
      setServerError(err.message);
      addToast(`Couldn't load support guides: ${err.message}`, 'error');
    } finally {
      setIsLoadingSupportGuides(false);
    }
  }, [addToast]);

  const retryConnection = useCallback(() => {
    setServerError(null);
    setIsLoadingDocs(true);
    setIsLoadingArchive(true);
    setIsLoadingRecent(true);
    fetchDocuments();
    fetchRecentAnalyses();
    fetchArchive();
    fetchSuggestedQuestions();
    fetchSettings();
    fetchSupportGuides();
  }, [fetchDocuments, fetchRecentAnalyses, fetchArchive, fetchSuggestedQuestions, fetchSettings, fetchSupportGuides]);

  // Initial load
  useEffect(() => {
    fetchDocuments();
    fetchRecentAnalyses();
    fetchArchive();
    fetchSuggestedQuestions();
    fetchSettings();
    fetchSupportGuides();
  }, [fetchDocuments, fetchRecentAnalyses, fetchArchive, fetchSuggestedQuestions, fetchSettings, fetchSupportGuides]);

  // Real-time polling for documents currently in "Processing" or "Uploading" state
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === 'Processing' || d.status === 'Uploading');
    if (!hasProcessing) return;

    const intervalId = setInterval(async () => {
      try {
        const updated = await api.getDocuments();
        setDocuments(updated);
        setServerError(null);
        const stillProcessing = updated.some((d) => d.status === 'Processing' || d.status === 'Uploading');
        if (!stillProcessing) {
          fetchSuggestedQuestions();
          addToast('Document indexing complete and ready for AI chat!', 'success');
        }
      } catch (err) {
        console.warn('Polling documents update failed:', err);
      }
    }, 2000);

    return () => clearInterval(intervalId);
  }, [documents, fetchSuggestedQuestions, addToast]);

  // -------------------------------------------------------------------------
  // Document Operations
  // -------------------------------------------------------------------------

  const uploadDocument = async (file, title = '') => {
    if (!file) {
      addToast('No file selected.', 'error');
      return;
    }

    if (file.size === 0) {
      addToast('The selected file is empty. Please choose a non-empty file.', 'error');
      return;
    }

    // Client-side guardrail on size (25MB)
    const maxBytes = 25 * 1024 * 1024;
    if (file.size > maxBytes) {
      const errText = `File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds 25MB limit.`;
      addToast(errText, 'error');
      throw new Error(errText);
    }

    try {
      const newDoc = await api.uploadDocument(file, title);
      setDocuments((prev) => [newDoc, ...prev.filter((d) => d.id !== newDoc.id)]);
      setSelectedScope(newDoc.name);
      setRecentlyUploadedDocId(newDoc.id);

      // Auto-clear recently uploaded highlight after 8 seconds
      setTimeout(() => {
        setRecentlyUploadedDocId((prev) => (prev === newDoc.id ? null : prev));
      }, 8000);

      addToast(`"${newDoc.name}" uploaded successfully! Indexing document...`, 'success');
      fetchSuggestedQuestions();
      return newDoc;
    } catch (err) {
      const msg = err.message || 'Upload failed. Please check the backend connection.';
      addToast(msg, 'error');
      throw err;
    }
  };

  const deleteDocument = async (docId) => {
    const doc = documents.find((d) => d.id === docId);
    try {
      await api.deleteDocument(docId, false);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      fetchArchive();
      fetchSuggestedQuestions();
      addToast(`"${doc?.name || 'Document'}" moved to Archive.`, 'info');
    } catch (err) {
      addToast(`Failed to archive document: ${err.message}`, 'error');
    }
  };

  const restoreArchivedItem = async (itemId) => {
    const item = archivedItems.find((i) => i.id === itemId);
    if (!item) return;

    try {
      if (item.type === 'document' && item.rawId) {
        await api.restoreDocument(item.rawId);
        addToast(`Restored "${item.title}" to Library.`, 'success');
      } else {
        addToast(`Restored "${item.title}".`, 'success');
      }
      fetchDocuments();
      fetchArchive();
      fetchSuggestedQuestions();
    } catch (err) {
      addToast(`Failed to restore item: ${err.message}`, 'error');
    }
  };

  const deleteArchivedItem = async (itemId) => {
    const item = archivedItems.find((i) => i.id === itemId);
    if (!item) return;

    try {
      if (item.type === 'document' && item.rawId) {
        await api.deleteDocument(item.rawId, true);
      } else if (item.rawId) {
        await api.deleteChatSession(item.rawId, true);
      }
      setArchivedItems((prev) => prev.filter((i) => i.id !== itemId));
      fetchDocuments();
      addToast(`Permanently deleted "${item.title}".`, 'info');
    } catch (err) {
      addToast(`Failed to delete permanently: ${err.message}`, 'error');
    }
  };

  // -------------------------------------------------------------------------
  // Chat Operations
  // -------------------------------------------------------------------------

  const sendChatMessage = async (text, scope = null) => {
    const queryText = text.trim();
    if (!queryText) return;
    if (isAiThinking) return; // Guard against rapid double-submits

    const activeScope = scope || selectedScope;

    const userMsg = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: queryText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setIsAiThinking(true);

    try {
      const response = await api.sendChatMessage(queryText, activeScope, currentSessionId);

      if (response.sessionId) {
        setCurrentSessionId(response.sessionId);
      }

      const assistantMsg = response.message || {
        id: `msg-${Date.now()}`,
        sender: 'assistant',
        intro: "I couldn't generate a response.",
        text: "I couldn't generate a response.",
        sections: [],
        sources: [],
        evidences: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setChatMessages((prev) => [...prev, assistantMsg]);
      fetchRecentAnalyses();
    } catch (err) {
      const errorMsg = {
        id: `msg-${Date.now()}`,
        sender: 'assistant',
        intro: err.message || 'Unable to connect to RAG backend.',
        text: err.message || 'Unable to connect to RAG backend.',
        sections: [],
        sources: [],
        evidences: [],
        noContext: true,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatMessages((prev) => [...prev, errorMsg]);
      addToast(`Chat error: ${err.message}`, 'error');
    } finally {
      setIsAiThinking(false);
    }
  };

  const startNewChat = () => {
    setChatMessages([]);
    setCurrentSessionId(null);
    addToast('Started a new conversation workspace.', 'info');
  };

  const loadChatSession = async (sessionId) => {
    try {
      const data = await api.getChatHistory(sessionId);
      setCurrentSessionId(sessionId);
      setChatMessages(data.messages || []);
      if (data.session?.doc_scope) {
        setSelectedScope(data.session.doc_scope);
      }
    } catch (err) {
      addToast(`Failed to load chat history: ${err.message}`, 'error');
    }
  };

  // -------------------------------------------------------------------------
  // Settings
  // -------------------------------------------------------------------------

  const updateUserSettings = async (updates) => {
    try {
      const updated = await api.updateSettings(updates);
      setUserSettings(updated);
      addToast('Settings saved.', 'success');
      return updated;
    } catch (err) {
      addToast(`Failed to save settings: ${err.message}`, 'error');
      throw err;
    }
  };

  const toggleNotification = async (key) => {
    const notifications = {
      ...userSettings.notifications,
      [key]: !userSettings.notifications?.[key]
    };
    await updateUserSettings({ notifications });
  };

  const togglePrivacy = async (key) => {
    const privacy = {
      ...userSettings.privacy,
      [key]: !userSettings.privacy?.[key]
    };
    await updateUserSettings({ privacy });
  };

  return (
    <AppContext.Provider
      value={{
        documents,
        isLoadingDocs,
        archivedItems,
        recentAnalyses,
        chatMessages,
        suggestedQuestions,
        supportGuides,
        currentSessionId,
        selectedScope,
        setSelectedScope,
        isAiThinking,
        isLoadingSettings,
        isLoadingSupportGuides,
        serverError,
        retryConnection,
        userSettings,
        isAvatarModalOpen,
        setIsAvatarModalOpen,
        isUploadModalOpen,
        setIsUploadModalOpen,
        isSupportModalOpen,
        setIsSupportModalOpen,
        mobileSidebarOpen,
        setMobileSidebarOpen,
        recentlyUploadedDocId,
        setRecentlyUploadedDocId,
        toasts,
        addToast,
        removeToast,
        fetchDocuments,
        fetchSettings,
        fetchSupportGuides,
        restoreArchivedItem,
        deleteArchivedItem,
        deleteDocument,
        uploadDocument,
        sendChatMessage,
        startNewChat,
        loadChatSession,
        updateUserSettings,
        toggleNotification,
        togglePrivacy
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
