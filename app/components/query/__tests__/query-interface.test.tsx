import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryInterface } from '../query-interface'
import { desktopAPI } from '@/lib/desktop-api'

// Mock the desktop API
jest.mock('@/lib/desktop-api', () => ({
  desktopAPI: {
    query: jest.fn(),
    createQueryStream: jest.fn(),
    search: jest.fn(),
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

describe('QueryInterface Component', () => {
  let user: ReturnType<typeof userEvent.setup>

  beforeEach(() => {
    user = userEvent.setup()
    jest.clearAllMocks()
    
    // Reset EventSource mock
    mockEventSource.onmessage = null
    mockEventSource.onerror = null
    mockEventSource.onopen = null
    jest.clearAllMocks()
    
    // Mock successful query response
    mockDesktopAPI.query.mockResolvedValue({
      response: 'Test response from backend',
      sources: [
        {
          id: '1',
          title: 'Test Document',
          content: 'Test content chunk',
          score: 0.95,
          metadata: { page: 1 }
        }
      ]
    })
  })

  describe('Component Rendering', () => {
    test('renders chat interface correctly', () => {
      render(<QueryInterface />)
      
      expect(screen.getByText('AI Chat')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('Ask me anything about your documents...')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
    })

    test('renders welcome message on mount', () => {
      render(<QueryInterface />)
      
      expect(screen.getByText(/Hello! I'm your personal AI assistant/)).toBeInTheDocument()
    })

    test('displays message timestamp and type indicators', () => {
      render(<QueryInterface />)
      
      // Check for Bot component in welcome message (using lucide-react Bot icon)
      expect(screen.getByTestId('bot-icon')).toBeInTheDocument()
    })
  })

  describe('Message Input and Submission', () => {
    test('enables send button when input has text', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      expect(sendButton).toBeDisabled()
      
      await user.type(input, 'Test query')
      expect(sendButton).toBeEnabled()
    })

    test('clears input after sending message', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      await user.type(input, 'Test query')
      await user.click(sendButton)
      
      expect(input).toHaveValue('')
    })

    test('prevents sending empty messages', async () => {
      render(<QueryInterface />)
      
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      await user.click(sendButton)
      
      expect(mockDesktopAPI.query).not.toHaveBeenCalled()
      expect(mockDesktopAPI.createQueryStream).not.toHaveBeenCalled()
    })

    test('handles form submission via Enter key', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      
      await user.type(input, 'Test query')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalledWith('Test query', expect.any(Object))
      })
    })

    test('disables input during loading state', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      const sendButton = screen.getByRole('button', { name: /send/i })
      
      await user.type(input, 'Test query')
      await user.click(sendButton)
      
      expect(input).toBeDisabled()
      expect(sendButton).toBeDisabled()
    })
  })

  describe('SSE Streaming Integration', () => {
    test('creates EventSource for streaming queries', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Test streaming query')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalledWith(
          'Test streaming query',
          expect.objectContaining({ top_k: expect.any(Number) })
        )
      })
    })

    test('handles streaming tokens from SSE', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Test streaming')
      await user.keyboard('{Enter}')
      
      // Wait for the EventSource to be created
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      // Simulate streaming messages
      const streamData = { token: 'Hello ', type: 'token' }
      act(() => {
        mockEventSource.onmessage?.({ data: JSON.stringify(streamData) } as MessageEvent)
      })
      
      await waitFor(() => {
        expect(screen.getByText(/Hello/)).toBeInTheDocument()
      })
      
      // Simulate more tokens
      const moreData = { token: 'world!', type: 'token' }
      act(() => {
        mockEventSource.onmessage?.({ data: JSON.stringify(moreData) } as MessageEvent)
      })
      
      await waitFor(() => {
        expect(screen.getByText(/Hello world!/)).toBeInTheDocument()
      })
    })

    test('handles stream completion event', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Complete test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      // Simulate streaming completion
      const completionData = { type: 'done', sources: [] }
      act(() => {
        mockEventSource.onmessage?.({ data: JSON.stringify(completionData) } as MessageEvent)
      })
      
      await waitFor(() => {
        // Check that loading state is cleared
        const input = screen.getByPlaceholderText('Ask me anything about your documents...')
        expect(input).not.toBeDisabled()
      })
    })

    test('handles SSE connection errors gracefully', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Error test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      // Simulate connection error
      act(() => {
        mockEventSource.onerror?.(new Event('error'))
      })
      
      await waitFor(() => {
        expect(screen.getByText(/connection error/i)).toBeInTheDocument()
      })
    })

    test('closes EventSource on component cleanup', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      const { unmount } = render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Cleanup test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      unmount()
      
      expect(mockEventSource.close).toHaveBeenCalled()
    })
  })

  describe('Source Attribution Display', () => {
    test('displays source information with streaming response', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Sources test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      // Simulate completion with sources
      const sourcesData = {
        type: 'done',
        sources: [
          {
            id: '1',
            title: 'Document 1.pdf',
            content: 'Relevant content from document',
            score: 0.95,
            metadata: { page: 1 }
          },
          {
            id: '2', 
            title: 'Document 2.pdf',
            content: 'More relevant content',
            score: 0.87,
            metadata: { page: 3 }
          }
        ]
      }
      
      act(() => {
        mockEventSource.onmessage?.({ data: JSON.stringify(sourcesData) } as MessageEvent)
      })
      
      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
        expect(screen.getByText('Document 2.pdf')).toBeInTheDocument()
        expect(screen.getByText(/Page 1/)).toBeInTheDocument()
        expect(screen.getByText(/Page 3/)).toBeInTheDocument()
      })
    })

    test('shows relevance scores for sources', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Score test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      const sourcesData = {
        type: 'done',
        sources: [
          {
            id: '1',
            title: 'High Score Doc.pdf',
            content: 'Content',
            score: 0.95,
            metadata: {}
          }
        ]
      }
      
      act(() => {
        mockEventSource.onmessage?.({ data: JSON.stringify(sourcesData) } as MessageEvent)
      })
      
      await waitFor(() => {
        expect(screen.getByText(/95%/)).toBeInTheDocument()
      })
    })

    test('handles empty sources gracefully', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'No sources')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      const noSourcesData = { type: 'done', sources: [] }
      
      act(() => {
        mockEventSource.onmessage?.({ data: JSON.stringify(noSourcesData) } as MessageEvent)
      })
      
      await waitFor(() => {
        expect(screen.getByText(/no relevant sources found/i)).toBeInTheDocument()
      })
    })
  })

  describe('Query History Management', () => {
    test('maintains conversation history', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      
      // First query
      await user.type(input, 'First query')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByText('First query')).toBeInTheDocument()
      })
      
      // Second query  
      await user.type(input, 'Second query')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByText('First query')).toBeInTheDocument()
        expect(screen.getByText('Second query')).toBeInTheDocument()
      })
    })

    test('persists conversation history to localStorage', async () => {
      const setItemSpy = jest.spyOn(Storage.prototype, 'setItem')
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Persist test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(setItemSpy).toHaveBeenCalledWith(
          'localrecall_chat_history',
          expect.stringContaining('Persist test')
        )
      })
      
      setItemSpy.mockRestore()
    })

    test('loads conversation history from localStorage', () => {
      const mockHistory = JSON.stringify([
        {
          id: 'saved-1',
          type: 'user',
          content: 'Saved query',
          timestamp: '2025-01-01T00:00:00Z'
        },
        {
          id: 'saved-2', 
          type: 'assistant',
          content: 'Saved response',
          timestamp: '2025-01-01T00:00:01Z'
        }
      ])
      
      const getItemSpy = jest.spyOn(Storage.prototype, 'getItem')
      getItemSpy.mockReturnValue(mockHistory)
      
      render(<QueryInterface />)
      
      expect(screen.getByText('Saved query')).toBeInTheDocument()
      expect(screen.getByText('Saved response')).toBeInTheDocument()
      
      getItemSpy.mockRestore()
    })

    test('provides clear history functionality', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Clear test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByText('Clear test')).toBeInTheDocument()
      })
      
      // Find and click clear history button
      const clearButton = screen.getByRole('button', { name: /clear history/i })
      await user.click(clearButton)
      
      expect(screen.queryByText('Clear test')).not.toBeInTheDocument()
      // Welcome message should still be present
      expect(screen.getByText(/Hello! I'm your personal AI assistant/)).toBeInTheDocument()
    })
  })

  describe('Message Actions and Feedback', () => {
    test('provides copy message functionality', async () => {
      // Mock clipboard API
      Object.assign(navigator, {
        clipboard: {
          writeText: jest.fn().mockResolvedValue(undefined),
        },
      })
      
      render(<QueryInterface />)
      
      // Look for copy button in welcome message
      const copyButtons = screen.getAllByRole('button', { name: /copy/i })
      expect(copyButtons.length).toBeGreaterThan(0)
      
      await user.click(copyButtons[0])
      
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        expect.stringContaining('Hello! I\'m your personal AI assistant')
      )
    })

    test('provides message feedback (thumbs up/down)', async () => {
      render(<QueryInterface />)
      
      const thumbsUpButtons = screen.getAllByRole('button', { name: /thumbs up/i })
      const thumbsDownButtons = screen.getAllByRole('button', { name: /thumbs down/i })
      
      expect(thumbsUpButtons.length).toBeGreaterThan(0)
      expect(thumbsDownButtons.length).toBeGreaterThan(0)
      
      await user.click(thumbsUpButtons[0])
      // Should show feedback confirmation
      expect(screen.getByText(/feedback recorded/i)).toBeInTheDocument()
    })

    test('displays loading indicators during query processing', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Loading test')
      await user.keyboard('{Enter}')
      
      // Should show loading dots
      await waitFor(() => {
        const loadingDots = screen.getByTestId('loading-dots')
        expect(loadingDots).toBeInTheDocument()
      })
    })
  })

  describe('Error Handling', () => {
    test('handles API query failures gracefully', async () => {
      mockDesktopAPI.createQueryStream.mockImplementation(() => {
        throw new Error('API Error')
      })
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Error test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByText(/error processing your request/i)).toBeInTheDocument()
      })
    })

    test('shows retry option after API failures', async () => {
      mockDesktopAPI.createQueryStream.mockRejectedValueOnce(new Error('Network error'))
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Retry test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
      })
      
      // Mock successful retry
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      const retryButton = screen.getByRole('button', { name: /retry/i })
      await user.click(retryButton)
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalledTimes(2)
      })
    })

    test('handles malformed streaming data', async () => {
      mockDesktopAPI.createQueryStream.mockReturnValue(mockEventSource as any)
      
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Malformed test')
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockDesktopAPI.createQueryStream).toHaveBeenCalled()
      })
      
      // Send malformed data
      act(() => {
        mockEventSource.onmessage?.({ data: 'invalid json' } as MessageEvent)
      })
      
      // Should not crash and should show error
      await waitFor(() => {
        expect(screen.getByText(/error parsing response/i)).toBeInTheDocument()
      })
    })
  })

  describe('Accessibility and Keyboard Navigation', () => {
    test('supports keyboard shortcuts', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      
      // Test Escape to clear input
      await user.type(input, 'Test text')
      await user.keyboard('{Escape}')
      expect(input).toHaveValue('')
    })

    test('provides proper ARIA labels and roles', () => {
      render(<QueryInterface />)
      
      const chatContainer = screen.getByRole('log')
      expect(chatContainer).toHaveAttribute('aria-live', 'polite')
      
      const input = screen.getByRole('textbox')
      expect(input).toHaveAttribute('aria-label', expect.stringContaining('message'))
    })

    test('announces new messages to screen readers', async () => {
      render(<QueryInterface />)
      
      const input = screen.getByPlaceholderText('Ask me anything about your documents...')
      await user.type(input, 'Accessibility test')
      await user.keyboard('{Enter}')
      
      // Should add announcement for new message
      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent(/new message/i)
      })
    })
  })
})