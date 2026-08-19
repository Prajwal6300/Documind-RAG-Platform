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
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [selectedScope, setSelectedScope] = useState('All Documents');
  
  const [isAiThinking, setIsAiThinking] = useState(false);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  
  // User Profile & Settings State
  const [userSettings, setUserSettings] = useState({
    name: "Enterprise Scholar",
    email: "analyst@documind.io",
    role: "Lead Document Architect",
    avatarUrl: "https://lh3.googleusercontent.com/aida-public/AB6AXuB1gOVA50bVGyZsmIs4PmAlqhe6Pr3jUSfKKhffffyJQv8KWlRad7I3SMR7p_0K-TI1M9bWJ4KZkNUJE2IQ5l33brWjL7umUbcxalw7Ponu_cYOA17myytdIiVliPvOy9sCrqKKukzJ8lAQA4tPl7ulAcAd0DJNifK3JxGEKLQPHTlmLUyomvBMXo87idne5YvLChyoSARtL9zv6CFh-4ACSO6_tFz-LGvMxc3nRT-A7-L_8GyK9Tj49g",
    avatarZoom: 110,
    avatarPos: { x: 0, y: 0 },
    plan: "Gemini RAG Enterprise",
    nextBilling: "Active",
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

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // -------------------------------------------------------------------------
  // Fetch Real Data from Backend
  // -------------------------------------------------------------------------

  const fetchDocuments = useCallback(async () => {
    try {
      const data = await api.getDocuments();
      setDocuments(data);
      setIsLoadingDocs(false);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
      setIsLoadingDocs(false);
    }
  }, []);

  const fetchRecentAnalyses = useCallback(async () => {
    try {
      const data = await api.getChatSessions();
      setRecentAnalyses(data);
    } catch (err) {
      console.error('Failed to fetch recent analyses:', err);
    }
  }, []);

  const fetchArchive = useCallback(async () => {
    try {
      const data = await api.getArchive();
      setArchivedItems(data);
    } catch (err) {
      console.error('Failed to fetch archive:', err);
    }
  }, []);

  const fetchSuggestedQuestions = useCallback(async () => {
    try {
      const data = await api.getSuggestedQuestions();
      setSuggestedQuestions(data);
    } catch (err) {
      console.error('Failed to fetch suggested questions:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchDocuments();
    fetchRecentAnalyses();
    fetchArchive();
    fetchSuggestedQuestions();
  }, [fetchDocuments, fetchRecentAnalyses, fetchArchive, fetchSuggestedQuestions]);

  // Real-time polling for documents currently in "Processing" state
  useEffect(() => {
    const hasProcessing = documents.some((d) => d.status === 'Processing');
    if (!hasProcessing) return;

    const pollInterval = setInterval(async () => {
      try {
        const updated = await api.getDocuments();
        setDocuments(updated);
        const stillProcessing = updated.some((d) => d.status === 'Processing');
        if (!stillProcessing) {
          fetchSuggestedQuestions();
          addToast('Document indexing completed!', 'success');
        }
      } catch (err) {
        console.error('Error polling documents:', err);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [documents, fetchSuggestedQuestions, addToast]);

  // -------------------------------------------------------------------------
  // Document Operations
  // -------------------------------------------------------------------------

  const uploadDocument = async (file, title = '') => {
    if (!file) {
      addToast('No file selected.', 'error');
      return;
    }

    // Client-side guardrail on size (25MB)
    const maxBytes = 25 * 1024 * 1024;
    if (file.size > maxBytes) {
      addToast(`File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds 25MB limit.`, 'error');
      return;
    }

    addToast(`Uploading "${file.name}"... indexing initiated.`, 'info');

    try {
      const newDoc = await api.uploadDocument(file, title);
      setDocuments((prev) => [newDoc, ...prev.filter((d) => d.id !== newDoc.id)]);
      fetchSuggestedQuestions();
    } catch (err) {
      addToast(`Upload failed: ${err.message}`, 'error');
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
      console.error('Chat error:', err);
      const errorMsg = {
        id: `msg-${Date.now()}`,
        sender: 'assistant',
        intro: `Error: ${err.message || 'Unable to connect to RAG backend.'}`,
        text: `Error: ${err.message || 'Unable to connect to RAG backend.'}`,
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

  const updateUserSettings = (updates) => {
    setUserSettings((prev) => ({ ...prev, ...updates }));
    addToast('Settings updated successfully.', 'success');
  };

  const toggleNotification = (key) => {
    setUserSettings((prev) => ({
      ...prev,
      notifications: {
        ...prev.notifications,
        [key]: !prev.notifications[key]
      }
    }));
    addToast('Updated notification preference.', 'info');
  };

  const togglePrivacy = (key) => {
    setUserSettings((prev) => ({
      ...prev,
      privacy: {
        ...prev.privacy,
        [key]: !prev.privacy[key]
      }
    }));
    addToast('Updated privacy preference.', 'info');
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
        currentSessionId,
        selectedScope,
        setSelectedScope,
        isAiThinking,
        userSettings,
        isAvatarModalOpen,
        setIsAvatarModalOpen,
        isUploadModalOpen,
        setIsUploadModalOpen,
        isSupportModalOpen,
        setIsSupportModalOpen,
        mobileSidebarOpen,
        setMobileSidebarOpen,
        toasts,
        addToast,
        removeToast,
        fetchDocuments,
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
