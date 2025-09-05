import '@testing-library/jest-dom'

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
}

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
}

// Mock localStorage
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}

// Mock fetch
global.fetch = jest.fn()

// Mock window.electronAPI for desktop app tests
global.window.electronAPI = {
  getBackendStatus: jest.fn(),
  onBackendStatus: jest.fn(),
  closeWindow: jest.fn(),
  minimizeWindow: jest.fn(),
  maximizeWindow: jest.fn(),
  removeAllListeners: jest.fn(),
  platform: 'darwin',
}

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn()

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn().mockResolvedValue(undefined),
    readText: jest.fn().mockResolvedValue(''),
  },
})

// Mock EventSource for SSE testing
global.EventSource = jest.fn(() => ({
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  close: jest.fn(),
  readyState: 1,
  onmessage: null,
  onerror: null,
  onopen: null,
}))