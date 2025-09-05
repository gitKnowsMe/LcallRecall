const { app, BrowserWindow, Menu, dialog, shell, ipcMain } = require('electron');
const path = require('path');
const isDev = process.env.NODE_ENV === 'development';
const { spawn } = require('child_process');
const os = require('os');

// Keep a global reference of the window object
let mainWindow;
let backendProcess = null;

// Backend configuration
const BACKEND_PORT = 8000;
const BACKEND_HOST = '127.0.0.1';

class BackendManager {
  constructor() {
    this.process = null;
    this.starting = false;
    this.ready = false;
  }

  async start() {
    if (this.starting || this.ready) return;
    
    // In development, check if backend is already running
    if (isDev) {
      try {
        const response = await fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/api/health-check`);
        if (response.ok) {
          console.log('Backend already running, skipping startup');
          this.ready = true;
          this.starting = false;
          
          if (mainWindow) {
            mainWindow.webContents.send('backend-status', { status: 'ready', port: BACKEND_PORT });
          }
          return;
        }
      } catch (error) {
        console.log('Backend not running, starting new instance...');
      }
    }
    
    console.log('Starting LocalRecall backend...');
    this.starting = true;

    try {
      const backendPath = path.join(__dirname, '..', 'backend');
      const pythonCmd = os.platform() === 'win32' ? 'python' : 'python3';
      
      this.process = spawn(pythonCmd, ['-m', 'uvicorn', 'app.main:app', '--host', BACKEND_HOST, '--port', BACKEND_PORT.toString()], {
        cwd: backendPath,
        stdio: ['pipe', 'pipe', 'pipe']
      });

      this.process.stdout.on('data', (data) => {
        const output = data.toString();
        console.log(`Backend: ${output}`);
        
        // Check if backend is ready
        if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
          this.ready = true;
          this.starting = false;
          
          // Notify renderer that backend is ready
          if (mainWindow) {
            mainWindow.webContents.send('backend-status', { status: 'ready', port: BACKEND_PORT });
          }
        }
      });

      this.process.stderr.on('data', (data) => {
        console.error(`Backend Error: ${data}`);
      });

      this.process.on('close', (code) => {
        console.log(`Backend process exited with code ${code}`);
        this.ready = false;
        this.starting = false;
        
        if (mainWindow) {
          mainWindow.webContents.send('backend-status', { status: 'stopped' });
        }
      });

      this.process.on('error', (error) => {
        console.error('Failed to start backend:', error);
        this.starting = false;
        
        if (mainWindow) {
          mainWindow.webContents.send('backend-status', { status: 'error', error: error.message });
        }
      });

    } catch (error) {
      console.error('Error starting backend:', error);
      this.starting = false;
    }
  }

  stop() {
    if (this.process) {
      console.log('Stopping backend...');
      this.process.kill();
      this.process = null;
      this.ready = false;
    }
  }

  isReady() {
    return this.ready;
  }
}

const backendManager = new BackendManager();

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 800,
    frame: false, // Completely remove native frame
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    },
    show: false, // Don't show until ready
    icon: path.join(__dirname, '..', 'resources', 'icon.png'),
  });

  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    // Open DevTools in development
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'app', 'build', 'index.html'));
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    // Focus on window
    if (isDev) {
      mainWindow.focus();
    }
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Prevent navigation to external URLs
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl);
    
    if (parsedUrl.origin !== 'http://localhost:3000' && parsedUrl.origin !== 'http://localhost:8000') {
      event.preventDefault();
    }
  });
}

// App event handlers
app.whenReady().then(async () => {
  createWindow();
  
  // Start backend
  await backendManager.start();
  
  // Set up application menu
  const template = require('./menu');
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Stop backend when app closes
  backendManager.stop();
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  // Stop backend before quitting
  backendManager.stop();
});

// IPC handlers
ipcMain.handle('get-backend-status', () => {
  return {
    ready: backendManager.isReady(),
    port: BACKEND_PORT,
    host: BACKEND_HOST
  };
});

ipcMain.handle('restart-backend', async () => {
  backendManager.stop();
  setTimeout(() => {
    backendManager.start();
  }, 2000);
});

// Handle app updates and other IPC messages
ipcMain.handle('app-version', () => {
  return app.getVersion();
});

// Window control handlers
ipcMain.handle('window-close', () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

ipcMain.handle('window-minimize', () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.handle('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.handle('show-message-box', async (event, options) => {
  const result = await dialog.showMessageBox(mainWindow, options);
  return result;
});

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    shell.openExternal(navigationUrl);
  });
});