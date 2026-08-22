/**
 * DocuMind API Client
 * Connects frontend to the FastAPI RAG backend.
 *
 * Every call handles: network failure (backend unreachable), timeouts, and
 * HTTP 4xx/5xx — each surfaced as a specific, user-readable Error message.
 */

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '');

if (!API_BASE_URL && import.meta.env.PROD) {
  console.error(
    '[DocuMind API Error] VITE_API_BASE_URL is not defined in this build!\n' +
    'API calls will fall back to relative paths on Vercel and fail with HTML 404/rewrite responses.\n' +
    'Please set VITE_API_BASE_URL=https://documind-rag-platform.onrender.com in Vercel Dashboard Settings -> Environment Variables and redeploy.'
  );
}

// Timeouts (ms). Chat can legitimately take a while (retrieval + generation).
const REQUEST_TIMEOUT = 15000;
const CHAT_TIMEOUT = 120000;
const UPLOAD_TIMEOUT = 300000;

export class ApiError extends Error {
  constructor(message, { status = null, code = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

/**
 * Fetch with an AbortController timeout. Never hangs indefinitely.
 */
async function fetchWithTimeout(url, options = {}, timeoutMs = REQUEST_TIMEOUT) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError('The request timed out. The server may be busy — please try again.', { code: 'timeout' });
    }
    // Network failure: backend down, proxy error, CORS rejection, DNS failure.
    throw new ApiError(
      "Can't connect to the DocuMind server. Check that the backend is running, then try again.",
      { code: 'network_error' }
    );
  } finally {
    clearTimeout(timer);
  }
}

async function handleResponse(response, timeoutMs = REQUEST_TIMEOUT) {
  if (!response.ok) {
    let errorDetail = '';
    let serverCode = null;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || '';
      serverCode = errJson.code || null;
    } catch {
      errorDetail = response.statusText || '';
    }

    let message = errorDetail;
    if (!message || message === 'Request failed') {
      if (response.status === 409) {
        message = 'A document with identical content or name already exists in the library.';
      } else if (response.status === 413) {
        message = 'File size exceeds the 25MB upload limit.';
      } else if (response.status === 415) {
        message = 'Unsupported file format. Please upload PDF, DOCX, XLSX, TXT, CSV, or PPTX.';
      } else if (response.status === 429) {
        message = 'Too many requests. Please wait a moment and try again.';
      } else if (response.status === 503) {
        message = 'The server is temporarily unavailable. Please try again in a moment.';
      } else if (response.status === 502 || response.status === 504) {
        message = 'The server took too long to respond. Please try again.';
      } else if (response.status >= 500) {
        message = 'Something went wrong on the server. Please try again.';
      } else {
        message = `Request failed (${response.status})`;
      }
    }

    throw new ApiError(message, { status: response.status, code: serverCode });
  }
  return response.json();
}

function checkStatus(res, timeoutMs) {
  return handleResponse(res, timeoutMs);
}

export const api = {
  // Document endpoints
  async getDocuments(includeArchived = false) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/documents?include_archived=${includeArchived}`);
    return checkStatus(res);
  },

  async uploadDocument(file, title = '') {
    const formData = new FormData();
    formData.append('file', file);
    if (title) {
      formData.append('title', title);
    }

    const res = await fetchWithTimeout(`${API_BASE_URL}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    }, UPLOAD_TIMEOUT);
    return checkStatus(res, UPLOAD_TIMEOUT);
  },

  async deleteDocument(docId, permanent = false) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/documents/${docId}?permanent=${permanent}`, {
      method: 'DELETE',
    });
    return checkStatus(res);
  },

  async archiveDocument(docId) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/documents/${docId}/archive`, {
      method: 'POST',
    });
    return checkStatus(res);
  },

  async restoreDocument(docId) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/documents/${docId}/restore`, {
      method: 'POST',
    });
    return checkStatus(res);
  },

  getDownloadUrl(docId) {
    return `${API_BASE_URL}/api/documents/${docId}/download`;
  },

  // Archive endpoint
  async getArchive() {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/archive`);
    return checkStatus(res);
  },

  // Chat endpoints
  async sendChatMessage(message, scope = 'All Documents', sessionId = null) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        scope,
        session_id: sessionId,
      }),
    }, CHAT_TIMEOUT);
    return checkStatus(res, CHAT_TIMEOUT);
  },

  async sendChatMessageStream(message, scope = 'All Documents', sessionId = null) {
    const url = `${API_BASE_URL}/api/chat/stream?message=${encodeURIComponent(message)}&scope=${encodeURIComponent(scope || 'All Documents')}&session_id=${sessionId || ''}`;
    const source = new EventSource(url, {
      withCredentials: true,
    });
    return new Promise((resolve, reject) => {
      let accumulatedText = '';
      let accumulatedGroundedness = null;
      let done = false;
      let error = null;

      source.onmessage = (event) => {
        const data = event.data;
        if (data.startsWith('data: ')) {
          const parsed = JSON.parse(data.substring(6));
          if (parsed.type === 'done') {
            done = true;
            source.close();
            resolve({
              text: accumulatedText,
              groundedness: accumulatedGroundedness,
              sessionId: sessionId,
              done: true,
            });
          } else if (parsed.type === 'metadata') {
            accumulatedGroundedness = parsed.groundedness;
            // Render metadata after done arrives
            // (handled by caller)
          } else if (parsed.type === 'error') {
            error = new Error(parsed.message || 'Streaming error');
            source.close();
            reject(error);
          } else if (parsed.type === 'token') {
            accumulatedText += parsed.token;
            // Notify caller of new token
            // (handled by caller via ontoken callback or state update)
          }
        }
      };

      source.onerror = (err) => {
        source.close();
        reject(new Error('SSE connection error') || 'Streaming connection failed');
      };
    });
  },

  async getChatSessions() {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/chat/sessions`);
    return checkStatus(res);
  },

  async getChatHistory(sessionId) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/chat/${sessionId}`);
    return checkStatus(res);
  },

  async deleteChatSession(sessionId, permanent = false) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/chat/sessions/${sessionId}?permanent=${permanent}`, {
      method: 'DELETE',
    });
    return checkStatus(res);
  },

  // Suggested questions
  async getSuggestedQuestions() {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/suggested-questions`);
    return checkStatus(res);
  },

  // System Health
  async getHealth() {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/health`, {}, 5000);
    return checkStatus(res);
  },

  async getLogs(lines = 40) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/logs?lines=${lines}`);
    return checkStatus(res);
  },

  async getSettings() {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/settings`);
    return checkStatus(res);
  },

  async updateSettings(updates) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/settings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    return checkStatus(res);
  },

  async getSupportGuides() {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/support/guides`);
    return checkStatus(res);
  },

  async submitSupportTicket(ticket) {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/support/tickets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ticket),
    });
    return checkStatus(res);
  },
};
