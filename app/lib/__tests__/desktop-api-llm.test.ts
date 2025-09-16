/**
 * Desktop API LLM Integration Tests
 * Tests the createLLMStream method and related functionality
 */

import { DesktopAPI } from '../desktop-api'

// Mock EventSource
const mockEventSource = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  close: jest.fn(),
  readyState: 1,
  onmessage: null,
  onerror: null,
  onopen: null,
}

Object.defineProperty(global, 'EventSource', {
  writable: true,
  value: jest.fn(() => mockEventSource),
})

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}

Object.defineProperty(global, 'localStorage', {
  value: mockLocalStorage,
})

describe('DesktopAPI LLM Integration', () => {
  let api: DesktopAPI
  const mockEventSourceConstructor = global.EventSource as jest.MockedClass<typeof EventSource>

  beforeEach(() => {
    jest.clearAllMocks()
    api = new DesktopAPI('http://localhost:8000')
    mockEventSourceConstructor.mockReturnValue(mockEventSource as any)
  })

  describe('createLLMStream', () => {
    it('creates EventSource with correct URL and default parameters', () => {
      const prompt = 'Hello AI'
      
      const eventSource = api.createLLMStream(prompt)
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        'http://localhost:8000/llm/stream?q=Hello%20AI&max_tokens=1024&temperature=0.7'
      )
      expect(eventSource).toBe(mockEventSource)
    })

    it('creates EventSource with custom parameters', () => {
      const prompt = 'Custom prompt'
      const options = { max_tokens: 512, temperature: 0.5 }
      
      api.createLLMStream(prompt, options)
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        'http://localhost:8000/llm/stream?q=Custom%20prompt&max_tokens=512&temperature=0.5'
      )
    })

    it('properly encodes special characters in prompt', () => {
      const prompt = 'Hello world! How are you? 100% good'
      
      api.createLLMStream(prompt)
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('q=Hello%20world%21%20How%20are%20you%3F%20100%25%20good')
      )
    })

    it('includes authentication token when available', () => {
      const testToken = 'test-jwt-token-123'
      mockLocalStorage.getItem.mockReturnValue(testToken)
      
      api.createLLMStream('Test prompt')
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining(`token=${testToken}`)
      )
    })

    it('works without authentication token', () => {
      mockLocalStorage.getItem.mockReturnValue(null)
      
      api.createLLMStream('No auth test')
      
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      expect(calledUrl).not.toContain('token=')
      expect(calledUrl).toContain('q=No%20auth%20test')
    })

    it('handles empty prompt', () => {
      api.createLLMStream('')
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('q=')
      )
    })

    it('validates parameter boundaries', () => {
      // Test minimum values
      api.createLLMStream('test', { max_tokens: 1, temperature: 0.0 })
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('max_tokens=1&temperature=0')
      )
      
      // Test maximum values  
      jest.clearAllMocks()
      api.createLLMStream('test', { max_tokens: 2048, temperature: 1.0 })
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('max_tokens=2048&temperature=1')
      )
    })

    it('handles partial options object', () => {
      // Only max_tokens specified
      api.createLLMStream('test', { max_tokens: 256 })
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('max_tokens=256&temperature=0.7')
      )
      
      jest.clearAllMocks()
      
      // Only temperature specified
      api.createLLMStream('test', { temperature: 0.3 })
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('max_tokens=1024&temperature=0.3')
      )
    })
  })

  describe('Base URL Configuration', () => {
    it('uses correct base URL for different environments', () => {
      const prodAPI = new DesktopAPI('https://api.example.com')
      
      prodAPI.createLLMStream('prod test')
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('https://api.example.com/llm/stream')
      )
    })

    it('handles base URL with trailing slash', () => {
      const apiWithSlash = new DesktopAPI('http://localhost:8000/')
      
      apiWithSlash.createLLMStream('slash test')
      
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      expect(calledUrl).toContain('http://localhost:8000/llm/stream')
      expect(calledUrl).not.toContain('//llm/stream')
    })

    it('handles base URL without protocol', () => {
      const apiNoProtocol = new DesktopAPI('localhost:8000')
      
      apiNoProtocol.createLLMStream('no protocol test')
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('localhost:8000/llm/stream')
      )
    })
  })

  describe('Authentication Token Handling', () => {
    it('retrieves token from localStorage', () => {
      const testToken = 'auth-token-456'
      mockLocalStorage.getItem.mockReturnValue(testToken)
      
      api.createLLMStream('auth test')
      
      expect(mockLocalStorage.getItem).toHaveBeenCalledWith('localrecall_token')
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining(`token=${testToken}`)
      )
    })

    it('handles missing token gracefully', () => {
      mockLocalStorage.getItem.mockReturnValue(null)
      
      expect(() => {
        api.createLLMStream('no token test')
      }).not.toThrow()
      
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      expect(calledUrl).not.toContain('token=')
    })

    it('handles empty token gracefully', () => {
      mockLocalStorage.getItem.mockReturnValue('')
      
      api.createLLMStream('empty token test')
      
      // Should not append empty token
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      expect(calledUrl).not.toContain('token=')
    })

    it('properly encodes token values', () => {
      const tokenWithSpecialChars = 'token+with/special=chars&more'
      mockLocalStorage.getItem.mockReturnValue(tokenWithSpecialChars)
      
      api.createLLMStream('encoding test')
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('token=token%2Bwith%2Fspecial%3Dchars%26more')
      )
    })
  })

  describe('Error Handling', () => {
    it('handles localStorage access errors', () => {
      mockLocalStorage.getItem.mockImplementation(() => {
        throw new Error('localStorage access denied')
      })
      
      expect(() => {
        api.createLLMStream('localStorage error test')
      }).not.toThrow()
      
      // Should still create EventSource without token
      expect(mockEventSourceConstructor).toHaveBeenCalled()
    })

    it('handles URL construction errors gracefully', () => {
      // Test with potentially problematic characters
      const problematicPrompt = 'test\n\r\t\0'
      
      expect(() => {
        api.createLLMStream(problematicPrompt)
      }).not.toThrow()
      
      expect(mockEventSourceConstructor).toHaveBeenCalled()
    })

    it('handles invalid parameter values', () => {
      // Test with potentially invalid numbers (should be handled by string conversion)
      const invalidOptions = { 
        max_tokens: NaN as any, 
        temperature: Infinity as any 
      }
      
      expect(() => {
        api.createLLMStream('invalid params', invalidOptions)
      }).not.toThrow()
      
      expect(mockEventSourceConstructor).toHaveBeenCalled()
    })
  })

  describe('URL Parameter Building', () => {
    it('builds parameters in correct order', () => {
      api.createLLMStream('order test', { max_tokens: 100, temperature: 0.2 })
      
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      const urlObj = new URL(calledUrl)
      
      expect(urlObj.searchParams.get('q')).toBe('order test')
      expect(urlObj.searchParams.get('max_tokens')).toBe('100')
      expect(urlObj.searchParams.get('temperature')).toBe('0.2')
    })

    it('handles parameter precedence correctly', () => {
      // Even if defaults are provided, explicit options should take precedence
      api.createLLMStream('precedence test', { max_tokens: 999 })
      
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      const urlObj = new URL(calledUrl)
      
      expect(urlObj.searchParams.get('max_tokens')).toBe('999')
      expect(urlObj.searchParams.get('temperature')).toBe('0.7') // default
    })

    it('maintains parameter types as strings', () => {
      api.createLLMStream('type test', { max_tokens: 42, temperature: 0.123 })
      
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      const urlObj = new URL(calledUrl)
      
      // URLSearchParams always stores as strings
      expect(typeof urlObj.searchParams.get('max_tokens')).toBe('string')
      expect(typeof urlObj.searchParams.get('temperature')).toBe('string')
      expect(urlObj.searchParams.get('max_tokens')).toBe('42')
      expect(urlObj.searchParams.get('temperature')).toBe('0.123')
    })
  })

  describe('Integration with EventSource', () => {
    it('returns the created EventSource instance', () => {
      const result = api.createLLMStream('test')
      
      expect(result).toBe(mockEventSource)
      expect(result).toHaveProperty('addEventListener')
      expect(result).toHaveProperty('close')
      expect(result).toHaveProperty('readyState')
    })

    it('preserves EventSource properties', () => {
      const eventSource = api.createLLMStream('properties test')
      
      expect(eventSource.readyState).toBe(1) // OPEN
      expect(typeof eventSource.addEventListener).toBe('function')
      expect(typeof eventSource.removeEventListener).toBe('function')
      expect(typeof eventSource.close).toBe('function')
    })

    it('allows for immediate event listener attachment', () => {
      const eventSource = api.createLLMStream('listener test')
      
      const messageHandler = jest.fn()
      const errorHandler = jest.fn()
      
      eventSource.addEventListener('message', messageHandler)
      eventSource.addEventListener('error', errorHandler)
      
      expect(mockEventSource.addEventListener).toHaveBeenCalledWith('message', messageHandler)
      expect(mockEventSource.addEventListener).toHaveBeenCalledWith('error', errorHandler)
    })
  })

  describe('Real-world Usage Scenarios', () => {
    it('supports typical chat interaction flow', () => {
      const userMessage = 'Hello, can you help me with coding?'
      const options = { max_tokens: 512, temperature: 0.6 }
      
      const eventSource = api.createLLMStream(userMessage, options)
      
      expect(eventSource).toBeDefined()
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('q=Hello%2C%20can%20you%20help%20me%20with%20coding%3F')
      )
    })

    it('handles follow-up questions in conversation', () => {
      // First message
      api.createLLMStream('What is Python?')
      
      // Follow-up message
      api.createLLMStream('Can you show me an example?', { max_tokens: 800 })
      
      expect(mockEventSourceConstructor).toHaveBeenCalledTimes(2)
    })

    it('supports code-related queries with special characters', () => {
      const codeQuery = 'How do I fix this error: "TypeError: Cannot read property \'length\' of undefined"?'
      
      api.createLLMStream(codeQuery)
      
      expect(mockEventSourceConstructor).toHaveBeenCalledWith(
        expect.stringContaining('TypeError%3A%20Cannot%20read%20property')
      )
    })

    it('handles long prompts appropriately', () => {
      const longPrompt = 'This is a very long prompt '.repeat(50) // ~1500 chars
      
      api.createLLMStream(longPrompt, { max_tokens: 1500 })
      
      expect(mockEventSourceConstructor).toHaveBeenCalled()
      const calledUrl = mockEventSourceConstructor.mock.calls[0][0]
      expect(calledUrl.length).toBeGreaterThan(1000)
    })

    it('maintains consistent behavior across multiple calls', () => {
      const prompts = [
        'First question',
        'Second question', 
        'Third question'
      ]
      
      prompts.forEach(prompt => {
        api.createLLMStream(prompt)
      })
      
      expect(mockEventSourceConstructor).toHaveBeenCalledTimes(3)
      
      // Verify each call was made correctly
      prompts.forEach((prompt, index) => {
        const calledUrl = mockEventSourceConstructor.mock.calls[index][0]
        expect(calledUrl).toContain(encodeURIComponent(prompt))
      })
    })
  })
})