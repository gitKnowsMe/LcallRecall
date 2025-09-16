// Desktop API client for LocalRecall Electron app

// Types for Electron API
declare global {
  interface Window {
    electronAPI?: {
      getBackendStatus: () => Promise<{ ready: boolean; port: number; host: string }>;
      restartBackend: () => Promise<void>;
      onBackendStatus: (callback: (data: { status: string; port?: number; error?: string }) => void) => void;
      getAppVersion: () => Promise<string>;
      showMessageBox: (options: any) => Promise<any>;
      platform: string;
      removeAllListeners: (channel: string) => void;
      closeWindow?: () => void;
      minimizeWindow?: () => void;
      maximizeWindow?: () => void;
      
      // Model detection methods
      detectModel: () => Promise<{
        found: boolean;
        path: string | null;
        info: any;
        error?: string;
      }>;
      selectModelFile: () => Promise<{
        success: boolean;
        path?: string;
        info?: any;
        error?: string;
        canceled?: boolean;
      }>;
      validateModel: (modelPath: string) => Promise<{
        valid: boolean;
        info?: any;
        error?: string;
      }>;
      getDownloadInstructions: () => Promise<any>;
      ensureModelsDirectory: () => Promise<{
        success: boolean;
        path?: string;
        error?: string;
      }>;
      openExternal: (url: string) => Promise<void>;
    };
  }
}

class DesktopAPI {
  private baseURL: string;
  private isElectron: boolean;

  constructor() {
    this.isElectron = typeof window !== 'undefined' && !!window.electronAPI;
    this.baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }

  // Check if running in Electron
  isDesktopApp(): boolean {
    return this.isElectron;
  }

  // Get backend status from Electron
  async getBackendStatus() {
    if (this.isElectron && window.electronAPI) {
      return await window.electronAPI.getBackendStatus();
    }
    
    // Fallback: try direct HTTP call
    try {
      const response = await fetch(`${this.baseURL}/health`);
      return {
        ready: response.ok,
        port: 8000,
        host: 'localhost'
      };
    } catch {
      return { ready: false, port: 8000, host: 'localhost' };
    }
  }

  // Listen for backend status changes
  onBackendStatusChange(callback: (status: any) => void) {
    if (this.isElectron && window.electronAPI) {
      window.electronAPI.onBackendStatus(callback);
    }
  }

  // Restart backend
  async restartBackend() {
    if (this.isElectron && window.electronAPI) {
      await window.electronAPI.restartBackend();
    }
  }

  // Get app version
  async getAppVersion(): Promise<string> {
    if (this.isElectron && window.electronAPI) {
      return await window.electronAPI.getAppVersion();
    }
    return '1.0.0';
  }

  // Show native message box
  async showMessageBox(options: {
    type?: 'none' | 'info' | 'error' | 'question' | 'warning';
    title?: string;
    message: string;
    detail?: string;
    buttons?: string[];
  }) {
    if (this.isElectron && window.electronAPI) {
      return await window.electronAPI.showMessageBox(options);
    }
    
    // Fallback to browser alert
    alert(`${options.title || 'LocalRecall'}\n${options.message}`);
    return { response: 0 };
  }

  // Platform info
  getPlatform(): string {
    if (this.isElectron && window.electronAPI) {
      return window.electronAPI.platform;
    }
    return typeof navigator !== 'undefined' ? navigator.platform : 'unknown';
  }

  // Clean up listeners
  removeAllListeners(channel: string) {
    if (this.isElectron && window.electronAPI) {
      window.electronAPI.removeAllListeners(channel);
    }
  }

  // HTTP API methods
  private async makeRequest(endpoint: string, options: RequestInit = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    // Add auth token if available
    const token = this.getAuthToken();
    if (token) {
      defaultOptions.headers = {
        ...defaultOptions.headers,
        'Authorization': `Bearer ${token}`,
      };
    }

    try {
      const response = await fetch(url, defaultOptions);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const contentType = response.headers.get('content-type');
      if (contentType?.includes('application/json')) {
        return await response.json();
      }
      
      return await response.text();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // Authentication methods
  private getAuthToken(): string | null {
    if (typeof localStorage !== 'undefined') {
      const token = localStorage.getItem('localrecall_token');
      // Add basic token validation
      if (token && token.length > 0) {
        return token;
      }
    }
    return null;
  }
  
  // Check if user is authenticated with valid token
  isAuthenticated(): boolean {
    const token = this.getAuthToken();
    return token !== null && token.length > 0;
  }
  
  // Validate token by making a quick API call
  async validateToken(): Promise<boolean> {
    try {
      await this.getCurrentUser();
      return true;
    } catch (error) {
      // Token is invalid or expired
      this.removeAuthToken();
      return false;
    }
  }

  private setAuthToken(token: string) {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('localrecall_token', token);
    }
  }

  private removeAuthToken() {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('localrecall_token');
    }
  }

  // Auth API
  async login(username: string, password: string) {
    const response = await this.makeRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    
    if (response.access_token) {
      this.setAuthToken(response.access_token);
    }
    
    return response;
  }

  async register(username: string, password: string) {
    const response = await this.makeRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    
    if (response.access_token) {
      this.setAuthToken(response.access_token);
    }
    
    return response;
  }

  async logout() {
    try {
      await this.makeRequest('/auth/logout', { method: 'POST' });
    } finally {
      this.removeAuthToken();
    }
  }

  async getCurrentUser() {
    return await this.makeRequest('/auth/me');
  }

  // Document API
  async uploadDocument(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    
    return await this.makeRequest('/documents/upload', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    });
  }

  async getDocuments() {
    return await this.makeRequest('/documents');
  }

  async deleteDocument(id: string) {
    return await this.makeRequest(`/documents/${id}`, {
      method: 'DELETE',
    });
  }

  // Query API
  async query(query: string, options: { top_k?: number } = {}) {
    return await this.makeRequest('/query/documents', {
      method: 'POST',
      body: JSON.stringify({ query, ...options }),
    });
  }

  // Streaming query using EventSource
  createQueryStream(query: string, options: { top_k?: number } = {}) {
    const params = new URLSearchParams({ 
      query, 
      ...Object.fromEntries(Object.entries(options).map(([k, v]) => [k, String(v)])) 
    });
    
    const token = this.getAuthToken();
    if (token) {
      params.append('token', token);
    }
    
    const url = `${this.baseURL}/query/stream?${params}`;
    
    // Create EventSource 
    const eventSource = new EventSource(url);
    
    return eventSource;
  }

  // Direct LLM streaming without RAG
  createLLMStream(prompt: string, options: { max_tokens?: number; temperature?: number } = {}) {
    const params = new URLSearchParams({ 
      q: prompt,  // Backend expects 'q' parameter, not 'prompt'
      max_tokens: String(options.max_tokens || 1024),
      temperature: String(options.temperature || 0.7)
    });
    
    const token = this.getAuthToken();
    if (token) {
      params.append('token', token);
    }
    
    const url = `${this.baseURL}/llm/stream?${params}`;
    
    // Create EventSource for direct LLM streaming
    const eventSource = new EventSource(url);
    
    return eventSource;
  }

  async search(query: string, options: { top_k?: number } = {}) {
    return await this.makeRequest('/query/search', {
      method: 'POST',
      body: JSON.stringify({ query, ...options }),
    });
  }

  // Health check
  async checkHealth() {
    return await this.makeRequest('/health');
  }

  async getStatus() {
    return await this.makeRequest('/status');
  }

  // Window controls (Electron only)
  closeWindow() {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.closeWindow) {
      window.electronAPI.closeWindow();
    }
  }

  minimizeWindow() {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.minimizeWindow) {
      window.electronAPI.minimizeWindow();
    }
  }

  maximizeWindow() {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.maximizeWindow) {
      window.electronAPI.maximizeWindow();
    }
  }

  // Model detection and management (Electron only)
  async detectModel() {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.detectModel) {
      return await window.electronAPI.detectModel();
    }
    
    // Fallback for web version
    return {
      found: false,
      path: null,
      info: null,
      error: 'Model detection not available in web version'
    };
  }

  async selectModelFile() {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.selectModelFile) {
      return await window.electronAPI.selectModelFile();
    }
    
    return {
      success: false,
      error: 'File selection not available in web version'
    };
  }

  async validateModel(modelPath: string) {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.validateModel) {
      return await window.electronAPI.validateModel(modelPath);
    }
    
    return {
      valid: false,
      error: 'Model validation not available in web version'
    };
  }

  async getDownloadInstructions() {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.getDownloadInstructions) {
      return await window.electronAPI.getDownloadInstructions();
    }
    
    return {
      modelName: 'Phi-2 Instruct GGUF',
      provider: 'Hugging Face',
      url: 'https://huggingface.co/microsoft/phi-2/tree/main',
      recommendedFile: 'phi-2.Q4_K_M.gguf',
      estimatedSize: '1.4GB'
    };
  }

  async ensureModelsDirectory() {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.ensureModelsDirectory) {
      return await window.electronAPI.ensureModelsDirectory();
    }
    
    return {
      success: false,
      error: 'Directory creation not available in web version'
    };
  }

  async openExternal(url: string) {
    if (this.isDesktopApp() && window.electronAPI && window.electronAPI.openExternal) {
      return await window.electronAPI.openExternal(url);
    }
    
    // Fallback: regular window.open
    window.open(url, '_blank');
  }
}

// Export singleton instance
export const desktopAPI = new DesktopAPI();
export default desktopAPI;