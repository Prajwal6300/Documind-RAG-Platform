/**
 * DocuMind API Client
 * Connects frontend to the FastAPI RAG backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = 'Request failed';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      errorDetail = response.statusText || errorDetail;
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export const api = {
  // Document endpoints
  async getDocuments(includeArchived = false) {
    const res = await fetch(`${API_BASE_URL}/api/documents?include_archived=${includeArchived}`);
    return handleResponse(res);
  },

  async uploadDocument(file, title = '') {
    const formData = new FormData();
    formData.append('file', file);
    if (title) {
      formData.append('title', title);
    }

    const res = await fetch(`${API_BASE_URL}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },

  async deleteDocument(docId, permanent = false) {
    const res = await fetch(`${API_BASE_URL}/api/documents/${docId}?permanent=${permanent}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },

  async archiveDocument(docId) {
    const res = await fetch(`${API_BASE_URL}/api/documents/${docId}/archive`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async restoreDocument(docId) {
    const res = await fetch(`${API_BASE_URL}/api/documents/${docId}/restore`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  getDownloadUrl(docId) {
    return `${API_BASE_URL}/api/documents/${docId}/download`;
  },

  // Archive endpoint
  async getArchive() {
    const res = await fetch(`${API_BASE_URL}/api/archive`);
    return handleResponse(res);
  },

  // Chat endpoints
  async sendChatMessage(message, scope = 'All Documents', sessionId = null) {
    const res = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        scope,
        session_id: sessionId,
      }),
    });
    return handleResponse(res);
  },

  async getChatSessions() {
    const res = await fetch(`${API_BASE_URL}/api/chat/sessions`);
    return handleResponse(res);
  },

  async getChatHistory(sessionId) {
    const res = await fetch(`${API_BASE_URL}/api/chat/${sessionId}`);
    return handleResponse(res);
  },

  async deleteChatSession(sessionId, permanent = false) {
    const res = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}?permanent=${permanent}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },

  // Suggested questions
  async getSuggestedQuestions() {
    const res = await fetch(`${API_BASE_URL}/api/suggested-questions`);
    return handleResponse(res);
  },

  // System Health
  async getHealth() {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    return handleResponse(res);
  },
};
