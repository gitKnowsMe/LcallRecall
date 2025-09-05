const { shell, app } = require('electron');
const isDev = process.env.NODE_ENV === 'development';

const template = [
  // macOS app menu
  ...(process.platform === 'darwin' ? [{
    label: app.getName(),
    submenu: [
      { role: 'about' },
      { type: 'separator' },
      { role: 'services' },
      { type: 'separator' },
      { role: 'hide' },
      { role: 'hideothers' },
      { role: 'unhide' },
      { type: 'separator' },
      { role: 'quit' }
    ]
  }] : []),
  
  // File menu
  {
    label: 'File',
    submenu: [
      {
        label: 'New Chat',
        accelerator: 'CmdOrCtrl+N',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'new-chat' });
          }
        }
      },
      { type: 'separator' },
      {
        label: 'Upload Document',
        accelerator: 'CmdOrCtrl+O',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'upload-document' });
          }
        }
      },
      { type: 'separator' },
      ...(process.platform === 'darwin' ? [
        { role: 'close' }
      ] : [
        { role: 'quit' }
      ])
    ]
  },
  
  // Edit menu
  {
    label: 'Edit',
    submenu: [
      { role: 'undo' },
      { role: 'redo' },
      { type: 'separator' },
      { role: 'cut' },
      { role: 'copy' },
      { role: 'paste' },
      { role: 'selectall' },
      { type: 'separator' },
      {
        label: 'Find in Documents',
        accelerator: 'CmdOrCtrl+F',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'find' });
          }
        }
      }
    ]
  },
  
  // View menu
  {
    label: 'View',
    submenu: [
      { role: 'reload' },
      { role: 'forceReload' },
      { role: 'toggleDevTools' },
      { type: 'separator' },
      { role: 'resetZoom' },
      { role: 'zoomIn' },
      { role: 'zoomOut' },
      { type: 'separator' },
      { role: 'togglefullscreen' },
      { type: 'separator' },
      {
        label: 'Chat View',
        accelerator: 'CmdOrCtrl+1',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'view-chat' });
          }
        }
      },
      {
        label: 'Documents View',
        accelerator: 'CmdOrCtrl+2',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'view-documents' });
          }
        }
      },
      {
        label: 'Knowledge Base',
        accelerator: 'CmdOrCtrl+3',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'view-knowledge' });
          }
        }
      }
    ]
  },
  
  // Tools menu
  {
    label: 'Tools',
    submenu: [
      {
        label: 'Restart Backend',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'restart-backend' });
          }
        }
      },
      {
        label: 'Check Backend Status',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'check-backend' });
          }
        }
      },
      { type: 'separator' },
      {
        label: 'Clear Chat History',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'clear-history' });
          }
        }
      },
      {
        label: 'Reset Application Data',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'reset-data' });
          }
        }
      }
    ]
  },
  
  // Window menu (macOS)
  ...(process.platform === 'darwin' ? [{
    label: 'Window',
    submenu: [
      { role: 'minimize' },
      { role: 'zoom' },
      { type: 'separator' },
      { role: 'front' },
      { type: 'separator' },
      { role: 'window' }
    ]
  }] : []),
  
  // Help menu
  {
    label: 'Help',
    submenu: [
      {
        label: 'About LocalRecall',
        click: () => {
          shell.openExternal('https://github.com/your-repo/LocalRecall');
        }
      },
      {
        label: 'Documentation',
        click: () => {
          shell.openExternal('https://docs.localrecall.com');
        }
      },
      {
        label: 'Report Issue',
        click: () => {
          shell.openExternal('https://github.com/your-repo/LocalRecall/issues');
        }
      },
      { type: 'separator' },
      {
        label: 'Keyboard Shortcuts',
        accelerator: 'CmdOrCtrl+?',
        click: (menuItem, browserWindow) => {
          if (browserWindow) {
            browserWindow.webContents.send('menu-action', { action: 'show-shortcuts' });
          }
        }
      }
    ]
  }
];

module.exports = template;