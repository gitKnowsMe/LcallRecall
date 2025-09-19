const { app, BrowserWindow, Menu, dialog, shell, ipcMain } = require('electron');
const path = require('path');
const isDev = process.env.NODE_ENV === 'development';
const { spawn } = require('child_process');
const os = require('os');
const ModelManager = require('./model-manager');

// Keep a global reference of the window object
let mainWindow;
let backendProcess = null;
let frontendProcess = null;

// Backend configuration
const BACKEND_PORT = 8000;
const BACKEND_HOST = '127.0.0.1';

// Frontend configuration
const FRONTEND_PORT = 3001;
const FRONTEND_HOST = '127.0.0.1';

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
      let backendExecutable, backendArgs, backendCwd;
      
      if (isDev) {
        // Development mode: Use Python + uvicorn
        backendCwd = path.join(__dirname, '..', 'backend');
        const pythonCmd = os.platform() === 'win32' ? 'python' : 'python3';
        backendExecutable = pythonCmd;
        backendArgs = ['-m', 'uvicorn', 'app.main:app', '--host', BACKEND_HOST, '--port', BACKEND_PORT.toString()];
      } else {
        // Production mode: Use bundled executable
        backendExecutable = path.join(process.resourcesPath, 'backend', 'localrecall-backend');
        backendArgs = ['--host', BACKEND_HOST, '--port', BACKEND_PORT.toString()];
        backendCwd = path.dirname(backendExecutable);
        
        // Set user data path for production databases
        const userDataPath = app.getPath('userData');
        process.env.LOCALRECALL_USER_DATA = userDataPath;

        // Set production config file path
        const configPath = path.join(path.dirname(backendExecutable), 'production-config.json');
        process.env.CONFIG_FILE = configPath;

        console.log(`Production backend path: ${backendExecutable}`);
        console.log(`Production config path: ${configPath}`);
        console.log(`User data path: ${userDataPath}`);
      }
      
      this.process = spawn(backendExecutable, backendArgs, {
        cwd: backendCwd,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env }
      });

      this.process.stdout.on('data', (data) => {
        const output = data.toString();
        try {
          console.log(`Backend: ${output}`);
        } catch (e) {
          // Ignore EPIPE errors when writing to closed streams
        }
      });

      // Start periodic health check instead of relying on stdout parsing
      this.startHealthCheck();

      this.process.stderr.on('data', (data) => {
        try {
          console.error(`Backend Error: ${data}`);
        } catch (e) {
          // Ignore EPIPE errors when writing to closed streams
        }
      });

      this.process.on('close', (code) => {
        try {
          console.log(`Backend process exited with code ${code}`);
        } catch (e) {
          // Ignore EPIPE errors when writing to closed streams
        }
        this.ready = false;
        this.starting = false;

        if (mainWindow) {
          try {
            mainWindow.webContents.send('backend-status', { status: 'stopped' });
          } catch (e) {
            // Window might be closed
          }
        }
      });

      this.process.on('error', (error) => {
        try {
          console.error('Failed to start backend:', error);
        } catch (e) {
          // Ignore EPIPE errors when writing to closed streams
        }
        this.starting = false;

        if (mainWindow) {
          try {
            mainWindow.webContents.send('backend-status', { status: 'error', error: error.message });
          } catch (e) {
            // Window might be closed
          }
        }
      });

    } catch (error) {
      try {
        console.error('Error starting backend:', error);
      } catch (e) {
        // Ignore EPIPE errors when writing to closed streams
      }
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

  startHealthCheck() {
    // Start checking backend health every 2 seconds
    const healthCheckInterval = setInterval(async () => {
      if (this.ready) {
        clearInterval(healthCheckInterval);
        return;
      }

      try {
        const response = await fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/health`);
        if (response.ok) {
          const data = await response.json();
          if (data.status === 'ok') {
            console.log('Backend health check passed - backend is ready');
            this.ready = true;
            this.starting = false;
            clearInterval(healthCheckInterval);

            // Notify renderer that backend is ready
            if (mainWindow) {
              mainWindow.webContents.send('backend-status', { status: 'ready', port: BACKEND_PORT });
            }
          }
        }
      } catch (error) {
        // Backend not ready yet, keep checking
        console.log('Backend health check failed, retrying...');
      }
    }, 2000);

    // Stop checking after 2 minutes max
    setTimeout(() => {
      clearInterval(healthCheckInterval);
      if (!this.ready) {
        console.error('Backend failed to start within timeout');
        if (mainWindow) {
          mainWindow.webContents.send('backend-status', { status: 'timeout' });
        }
      }
    }, 120000);
  }
}

class FrontendManager {
  constructor() {
    this.process = null;
    this.starting = false;
    this.ready = false;
  }

  async start() {
    if (this.starting || this.ready) return;

    console.log('Starting LocalRecall frontend...');
    this.starting = true;

    try {
      let frontendCwd = path.join(__dirname, '..', 'app');

      if (isDev) {
        // Development mode: use npm run dev
        this.process = spawn('npm', ['run', 'dev'], {
          cwd: frontendCwd,
          stdio: ['pipe', 'pipe', 'pipe'],
          env: { ...process.env }
        });
      } else {
        // Production mode: use npm start
        this.process = spawn('npm', ['start'], {
          cwd: frontendCwd,
          stdio: ['pipe', 'pipe', 'pipe'],
          env: { ...process.env, PORT: FRONTEND_PORT.toString() }
        });
      }

      this.process.stdout.on('data', (data) => {
        const output = data.toString();
        console.log(`Frontend: ${output}`);

        // Check if frontend is ready
        if (output.includes('Ready') || output.includes('ready')) {
          this.ready = true;
          this.starting = false;
        }
      });

      this.process.stderr.on('data', (data) => {
        console.error(`Frontend Error: ${data}`);
      });

      this.process.on('close', (code) => {
        console.log(`Frontend process exited with code ${code}`);
        this.ready = false;
        this.starting = false;
      });

      this.process.on('error', (error) => {
        console.error('Failed to start frontend:', error);
        this.starting = false;
      });

    } catch (error) {
      console.error('Error starting frontend:', error);
      this.starting = false;
    }
  }

  stop() {
    if (this.process) {
      console.log('Stopping frontend...');
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
const frontendManager = new FrontendManager();

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
    // In production, load static files directly
    const htmlPath = path.join(__dirname, '..', 'app', 'build', 'index.html');
    console.log('Loading frontend from:', htmlPath);
    mainWindow.loadFile(htmlPath);
    // Enable dev tools for debugging
    mainWindow.webContents.openDevTools();
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

  // Start backend server
  backendManager.start(); // Non-blocking - window shows immediately

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

// Model detection and management handlers
ipcMain.handle('detect-model', async () => {
  try {
    const modelPath = await ModelManager.detectModel();
    
    if (modelPath) {
      const modelInfo = await ModelManager.getModelInfo(modelPath);
      return {
        found: true,
        path: modelPath,
        info: modelInfo
      };
    } else {
      return {
        found: false,
        path: null,
        info: null
      };
    }
  } catch (error) {
    console.error('Model detection error:', error);
    return {
      found: false,
      path: null,
      info: null,
      error: error.message
    };
  }
});

ipcMain.handle('select-model-file', async () => {
  try {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Select Phi-2 Model File',
      filters: [
        { name: 'GGUF Model Files', extensions: ['gguf'] },
        { name: 'All Files', extensions: ['*'] }
      ],
      properties: ['openFile']
    });

    if (result.canceled || !result.filePaths.length) {
      return { success: false, canceled: true };
    }

    const selectedPath = result.filePaths[0];
    
    // Validate the selected model
    const isValid = await ModelManager.validateModel(selectedPath);
    if (!isValid) {
      return {
        success: false,
        error: 'Selected file does not appear to be a valid Phi-2 model'
      };
    }

    const modelInfo = await ModelManager.getModelInfo(selectedPath);
    return {
      success: true,
      path: selectedPath,
      info: modelInfo
    };
  } catch (error) {
    console.error('File selection error:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('validate-model', async (_event, modelPath) => {
  try {
    const isValid = await ModelManager.validateModel(modelPath);
    const modelInfo = await ModelManager.getModelInfo(modelPath);
    
    return {
      valid: isValid,
      info: modelInfo
    };
  } catch (error) {
    return {
      valid: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-download-instructions', () => {
  return ModelManager.getDownloadInstructions();
});

ipcMain.handle('ensure-models-directory', async () => {
  try {
    const modelsDir = await ModelManager.ensureModelsDirectory();
    return {
      success: true,
      path: modelsDir
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('open-external', (_event, url) => {
  shell.openExternal(url);
});

// Security: Prevent new window creation
app.on('web-contents-created', (_event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    shell.openExternal(navigationUrl);
  });
});