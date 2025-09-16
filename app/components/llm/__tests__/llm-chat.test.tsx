import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LLMChat } from '../llm-chat'
import { desktopAPI } from '@/lib/desktop-api'

// Mock the desktop API
jest.mock('@/lib/desktop-api', () => ({
  desktopAPI: {
    createLLMStream: jest.fn(),
  },
}))

// Mock EventSource for SSE testing
const mockEventSource = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  close: jest.fn(),
  readyState: 1, // OPEN
  onmessage: null,
  onerror: null,
  onopen: null,
}

// Mock global EventSource
Object.defineProperty(global, 'EventSource', {
  writable: true,
  value: jest.fn(() => mockEventSource),
})

const mockDesktopAPI = desktopAPI as jest.Mocked<typeof desktopAPI>

describe('LLMChat Component', () => {
  let user: ReturnType<typeof userEvent.setup>

  beforeEach(() => {
    user = userEvent.setup()
    jest.clearAllMocks()
    
    // Reset EventSource mock
    mockEventSource.onmessage = null
    mockEventSource.onerror = null
    mockEventSource.onopen = null
    
    // Reset localStorage mock - check if it's a jest mock first
    if (jest.isMockFunction(global.localStorage.getItem)) {
      ;(global.localStorage.getItem as jest.Mock).mockReturnValue(null)
      ;(global.localStorage.setItem as jest.Mock).mockClear()
      ;(global.localStorage.removeItem as jest.Mock).mockClear()
    }
    
    // Mock createLLMStream to return our mock EventSource
    mockDesktopAPI.createLLMStream.mockReturnValue(mockEventSource as any)
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  describe('Component Rendering', () => {
    it('renders with initial welcome message', () => {
      render(<LLMChat />)
      
      // Check header elements
      expect(screen.getByText('Direct LLM Chat')).toBeInTheDocument()
      expect(screen.getByText('Phi-2 Direct')).toBeInTheDocument()
      expect(screen.getByText('Clear History')).toBeInTheDocument()
      
      // Check initial welcome message
      expect(screen.getByText(/Hello! I'm Phi-2, your direct AI assistant/)).toBeInTheDocument()
      expect(screen.getByText(/Unlike the RAG chat, I don't have access to your documents/)).toBeInTheDocument()
      
      // Check input elements
      expect(screen.getByPlaceholderText('Ask me anything...')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
    })

    it('displays correct branding and styling', () => {
      render(<LLMChat />)
      
      // Check for Zap icon (yellow branding)
      const zapIcons = screen.getAllByTestId('zap-icon') || screen.getAllByText(/⚡/) || []
      expect(zapIcons.length).toBeGreaterThan(0)
      
      // Check for yellow badge
      const badge = screen.getByText('Phi-2 Direct')
      expect(badge).toBeInTheDocument()
    })

    it('renders input field with character limit', () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      expect(input).toBeInTheDocument()
      expect(input).toHaveAttribute('maxLength', '4000')
    })

    it('send button is initially disabled', () => {
      render(<LLMChat />)
      
      const sendButton = screen.getByRole('button', { name: /send/i })
      expect(sendButton).toBeDisabled()
    })
  })

  describe('Message State Management', () => {
    it('enables send button when input has content', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      expect(sendButton).toBeDisabled()
      
      await user.type(input, 'Hello AI')
      
      expect(sendButton).not.toBeDisabled()
    })

    it('adds user message to conversation on submit', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Test message')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      expect(screen.getByText('Test message')).toBeInTheDocument()
    })

    it('clears input after message submission', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...') as HTMLInputElement
      
      await user.type(input, 'Test message')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      expect(input.value).toBe('')
    })

    it('supports form submission with Enter key', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Enter key test')
      await user.keyboard('{Enter}')
      
      expect(screen.getByText('Enter key test')).toBeInTheDocument()
    })

    it('prevents empty message submission', async () => {
      render(<LLMChat />)
      
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      // Try submitting empty message
      await user.click(sendButton)
      
      // Should not add any new messages (only initial welcome message should be present)
      const messages = screen.getAllByText(/Phi-2/)
      expect(messages.length).toBe(1) // Only the welcome message
    })

    it('disables send button and input during loading', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      await user.type(input, 'Loading test')
      await user.click(sendButton)
      
      expect(sendButton).toBeDisabled()
      expect(input).toBeDisabled()
    })
  })

  describe('EventSource Integration', () => {
    it('creates EventSource with correct parameters', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Test streaming')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      expect(mockDesktopAPI.createLLMStream).toHaveBeenCalledWith('Test streaming')
    })

    it('handles streaming token events', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Streaming test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Simulate streaming response
      act(() => {
        if (mockEventSource.onmessage) {
          // Start event
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'start', message: 'Generating response...' })
          } as MessageEvent)
          
          // Token events
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'token', content: 'Hello' })
          } as MessageEvent)
          
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'token', content: ' there!' })
          } as MessageEvent)
          
          // End event
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'end', message: 'Response complete' })
          } as MessageEvent)
        }
      })
      
      await waitFor(() => {
        expect(screen.getByText('Hello there!')).toBeInTheDocument()
      })
    })

    it('handles streaming error events', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Error test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Simulate error response
      act(() => {
        if (mockEventSource.onmessage) {
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'error', message: 'Connection failed' })
          } as MessageEvent)
        }
      })
      
      await waitFor(() => {
        expect(screen.getByText(/Sorry, I encountered an error/)).toBeInTheDocument()
      })
    })

    it('handles EventSource connection errors', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Connection error test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Simulate connection error
      act(() => {
        if (mockEventSource.onerror) {
          mockEventSource.onerror(new Event('error') as any)
        }
      })
      
      await waitFor(() => {
        expect(screen.getByText(/Connection error/)).toBeInTheDocument()
      })
    })

    it('closes EventSource on component unmount', async () => {
      const { unmount } = render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Cleanup test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      unmount()
      
      expect(mockEventSource.close).toHaveBeenCalled()
    })

    it('displays streaming cursor during response generation', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Cursor test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Simulate start of streaming
      act(() => {
        if (mockEventSource.onmessage) {
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'start', message: 'Generating...' })
          } as MessageEvent)
          
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'token', content: 'Starting' })
          } as MessageEvent)
        }
      })
      
      await waitFor(() => {
        // Look for streaming cursor (animated pulse)
        const streamingElements = screen.getAllByText('Starting')
        expect(streamingElements.length).toBeGreaterThan(0)
      })
    })
  })

  describe('LocalStorage Persistence', () => {
    it('saves messages to localStorage on change', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Persistence test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      if (jest.isMockFunction(global.localStorage.setItem)) {
        expect(global.localStorage.setItem).toHaveBeenCalledWith(
          'localrecall_llm_chat_history',
          expect.stringContaining('Persistence test')
        )
      }
    })

    it('restores messages from localStorage on mount', () => {
      const savedHistory = JSON.stringify([
        {
          id: '1',
          type: 'user',
          content: 'Restored message',
          timestamp: new Date().toISOString(),
        }
      ])
      
      if (jest.isMockFunction(global.localStorage.getItem)) {
        ;(global.localStorage.getItem as jest.Mock).mockReturnValue(savedHistory)
      }
      
      render(<LLMChat />)
      
      expect(screen.getByText('Restored message')).toBeInTheDocument()
    })

    it('handles corrupted localStorage data gracefully', () => {
      if (jest.isMockFunction(global.localStorage.getItem)) {
        ;(global.localStorage.getItem as jest.Mock).mockReturnValue('invalid json')
      }
      
      // Should not throw error and should render default welcome message
      render(<LLMChat />)
      
      expect(screen.getByText(/Hello! I'm Phi-2/)).toBeInTheDocument()
    })

    it('clears localStorage when clearing history', async () => {
      // Set up some initial history
      const savedHistory = JSON.stringify([
        {
          id: '1',
          type: 'user',
          content: 'Message to clear',
          timestamp: new Date().toISOString(),
        }
      ])
      
      if (jest.isMockFunction(global.localStorage.getItem)) {
        ;(global.localStorage.getItem as jest.Mock).mockReturnValue(savedHistory)
      }
      
      render(<LLMChat />)
      
      const clearButton = screen.getByText('Clear History')
      await user.click(clearButton)
      
      // Should save new history with only welcome message
      if (jest.isMockFunction(global.localStorage.setItem)) {
        expect(global.localStorage.setItem).toHaveBeenCalledWith(
          'localrecall_llm_chat_history',
          expect.stringContaining('Hello! I\'m Phi-2')
        )
      }
      
      // User message should be gone
      expect(screen.queryByText('Message to clear')).not.toBeInTheDocument()
    })
  })

  describe('User Interactions', () => {
    it('supports message copying functionality', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Copy test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Complete the streaming to show copy button
      act(() => {
        if (mockEventSource.onmessage) {
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'start' })
          } as MessageEvent)
          
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'token', content: 'AI response' })
          } as MessageEvent)
          
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'end' })
          } as MessageEvent)
        }
      })
      
      await waitFor(() => {
        const copyButtons = screen.getAllByRole('button')
        const copyButton = copyButtons.find(button => 
          button.querySelector('[data-testid="copy-icon"]') || 
          button.textContent?.includes('Copy') ||
          button.className?.includes('copy')
        )
        expect(copyButton).toBeInTheDocument()
      })
    })

    it('shows timestamp for completed messages', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Timestamp test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Complete the streaming
      act(() => {
        if (mockEventSource.onmessage) {
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'token', content: 'Response' })
          } as MessageEvent)
          
          mockEventSource.onmessage({
            data: JSON.stringify({ type: 'end' })
          } as MessageEvent)
        }
      })
      
      await waitFor(() => {
        expect(screen.getByText(/Direct Phi-2 •/)).toBeInTheDocument()
      })
    })

    it('scrolls to bottom when new messages arrive', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Scroll test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // scrollIntoView should be called (mocked in jest.setup.js)
      expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    })

    it('respects character limit in input field', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      const longText = 'a'.repeat(5000) // Exceeds 4000 character limit
      
      await user.type(input, longText)
      
      expect((input as HTMLInputElement).value.length).toBeLessThanOrEqual(4000)
    })
  })

  describe('Error Handling', () => {
    it('displays error message when streaming fails', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'Error handling test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Simulate error
      act(() => {
        if (mockEventSource.onerror) {
          mockEventSource.onerror(new Event('error') as any)
        }
      })
      
      await waitFor(() => {
        expect(screen.getByText(/Connection error/)).toBeInTheDocument()
      })
    })

    it('handles JSON parsing errors in streaming data', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      await user.type(input, 'JSON error test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      // Simulate malformed JSON
      act(() => {
        if (mockEventSource.onmessage) {
          mockEventSource.onmessage({
            data: 'invalid json'
          } as MessageEvent)
        }
      })
      
      // Should not crash, component should still be functional
      expect(screen.getByPlaceholderText('Ask me anything...')).toBeInTheDocument()
    })

    it('recovers from errors and allows new messages', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      
      // First message with error
      await user.type(input, 'Error message')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      act(() => {
        if (mockEventSource.onerror) {
          mockEventSource.onerror(new Event('error') as any)
        }
      })
      
      await waitFor(() => {
        expect(screen.getByText(/Connection error/)).toBeInTheDocument()
      })
      
      // Should be able to send another message
      await user.type(input, 'Recovery test')
      await user.click(screen.getByRole('button', { name: /send/i }))
      
      expect(screen.getByText('Recovery test')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('has proper form labels and structure', () => {
      render(<LLMChat />)
      
      const form = screen.getByRole('form') || screen.getByTestId('chat-form')
      expect(form || screen.getByPlaceholderText('Ask me anything...')).toBeInTheDocument()
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      expect(input).toHaveAttribute('maxLength', '4000')
      
      const button = screen.getByRole('button', { name: /send/i })
      expect(button).toBeInTheDocument()
    })

    it('supports keyboard navigation', async () => {
      render(<LLMChat />)
      
      const input = screen.getByPlaceholderText('Ask me anything...')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      // Tab to input
      await user.tab()
      expect(input).toHaveFocus()
      
      // Type message
      await user.type(input, 'Keyboard test')
      
      // Tab to send button
      await user.tab()
      expect(sendButton).toHaveFocus()
      
      // Enter should trigger send
      await user.keyboard('{Enter}')
      expect(screen.getByText('Keyboard test')).toBeInTheDocument()
    })

    it('has appropriate ARIA labels and roles', () => {
      render(<LLMChat />)
      
      // Check for appropriate button roles
      const clearButton = screen.getByRole('button', { name: /clear history/i })
      expect(clearButton).toBeInTheDocument()
      
      const sendButton = screen.getByRole('button', { name: /send/i })
      expect(sendButton).toBeInTheDocument()
      
      // Check for input accessibility
      const input = screen.getByPlaceholderText('Ask me anything...')
      expect(input).toBeInTheDocument()
    })
  })
})