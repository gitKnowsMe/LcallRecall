const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Backend management
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  onBackendStatus: (callback) => {
    ipcRenderer.on('backend-status', (event, data) => callback(data));
  },
  
  // App info
  getAppVersion: () => ipcRenderer.invoke('app-version'),
  
  // Dialogs
  showMessageBox: (options) => ipcRenderer.invoke('show-message-box', options),
  
  // Platform info
  platform: process.platform,
  
  // Remove listeners
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  },
  
  // Window controls
  closeWindow: () => ipcRenderer.invoke('window-close'),
  minimizeWindow: () => ipcRenderer.invoke('window-minimize'),
  maximizeWindow: () => ipcRenderer.invoke('window-maximize')
});

// Set up secure communication channel
window.addEventListener('DOMContentLoaded', () => {
  // Add desktop app class to body for CSS targeting
  document.body.classList.add('desktop-app');
  
  // Set up any desktop-specific styling or behavior
  if (process.platform === 'darwin') {
    document.body.classList.add('platform-mac');
  } else if (process.platform === 'win32') {
    document.body.classList.add('platform-windows');
  } else {
    document.body.classList.add('platform-linux');
  }
});