import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DocumentUpload } from '../document-upload'
import { desktopAPI } from '@/lib/desktop-api'

// Mock the desktop API
jest.mock('@/lib/desktop-api', () => ({
  desktopAPI: {
    uploadDocument: jest.fn(),
    getDocuments: jest.fn(),
    deleteDocument: jest.fn(),
  },
}))

// Mock react-dropzone
jest.mock('react-dropzone', () => ({
  useDropzone: jest.fn(() => ({
    getRootProps: () => ({
      'data-testid': 'dropzone',
    }),
    getInputProps: () => ({
      'data-testid': 'file-input',
    }),
    isDragActive: false,
  })),
}))

const mockDesktopAPI = desktopAPI as jest.Mocked<typeof desktopAPI>

describe('DocumentUpload Component', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    
    // Mock successful document fetch
    mockDesktopAPI.getDocuments.mockResolvedValue({
      documents: [
        {
          id: '1',
          filename: 'test-doc.pdf',
          title: 'Test Document',
          file_size: 1024000,
          upload_date: '2025-01-03T10:00:00Z',
          processing_status: 'completed',
        },
      ],
    })
  })

  describe('Component Rendering', () => {
    test('renders upload interface correctly', () => {
      render(<DocumentUpload />)
      
      expect(screen.getByText('Upload')).toBeInTheDocument()
      expect(screen.getByText('Upload Documents')).toBeInTheDocument()
      expect(screen.getByText('Drop files here or click to browse')).toBeInTheDocument()
      expect(screen.getByText('Supports PDF, Markdown, TXT, DOCX, and more')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /browse files/i })).toBeInTheDocument()
    })

    test('renders document library section', () => {
      render(<DocumentUpload />)
      
      expect(screen.getByText('Document Library')).toBeInTheDocument()
    })

    test('displays loading state initially', async () => {
      mockDesktopAPI.getDocuments.mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve({ documents: [] }), 100))
      )
      
      render(<DocumentUpload />)
      
      expect(screen.getByText('Loading documents...')).toBeInTheDocument()
      
      await waitFor(() => {
        expect(screen.queryByText('Loading documents...')).not.toBeInTheDocument()
      })
    })
  })

  describe('File Upload Functionality', () => {
    test('handles file drop successfully', async () => {
      const mockFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' })
      mockDesktopAPI.uploadDocument.mockResolvedValue({
        id: '2',
        filename: 'test.pdf',
        status: 'uploaded',
      })

      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      let onDropCallback: (files: File[]) => void
      mockUseDropzone.mockImplementation(({ onDrop }: { onDrop: (files: File[]) => void }) => {
        onDropCallback = onDrop
        return {
          getRootProps: () => ({ 'data-testid': 'dropzone' }),
          getInputProps: () => ({ 'data-testid': 'file-input' }),
          isDragActive: false,
        }
      })

      render(<DocumentUpload />)
      
      // Simulate file drop
      onDropCallback!([mockFile])

      await waitFor(() => {
        expect(mockDesktopAPI.uploadDocument).toHaveBeenCalledWith(mockFile)
      })
    })

    test('displays upload progress', async () => {
      const mockFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' })
      
      // Mock upload that takes time
      mockDesktopAPI.uploadDocument.mockImplementation(
        () => new Promise(resolve => 
          setTimeout(() => resolve({
            id: '2',
            filename: 'test.pdf',
            status: 'uploaded',
          }), 100)
        )
      )

      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      let onDropCallback: (files: File[]) => void
      mockUseDropzone.mockImplementation(({ onDrop }: { onDrop: (files: File[]) => void }) => {
        onDropCallback = onDrop
        return {
          getRootProps: () => ({ 'data-testid': 'dropzone' }),
          getInputProps: () => ({ 'data-testid': 'file-input' }),
          isDragActive: false,
        }
      })

      render(<DocumentUpload />)
      
      // Wait for initial loading to complete
      await waitFor(() => {
        expect(screen.queryByText('Loading documents...')).not.toBeInTheDocument()
      })
      
      // Simulate file drop
      await act(async () => {
        onDropCallback!([mockFile])
      })

      // Should show uploading state
      await waitFor(() => {
        expect(screen.getByText('Uploading...')).toBeInTheDocument()
      })

      // Wait for upload to complete
      await waitFor(() => {
        expect(screen.queryByText('Uploading...')).not.toBeInTheDocument()
      }, { timeout: 2000 })
    })

    test('handles upload error gracefully', async () => {
      const mockFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' })
      mockDesktopAPI.uploadDocument.mockRejectedValue(new Error('Upload failed'))

      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      let onDropCallback: (files: File[]) => void
      mockUseDropzone.mockImplementation(({ onDrop }: { onDrop: (files: File[]) => void }) => {
        onDropCallback = onDrop
        return {
          getRootProps: () => ({ 'data-testid': 'dropzone' }),
          getInputProps: () => ({ 'data-testid': 'file-input' }),
          isDragActive: false,
        }
      })

      render(<DocumentUpload />)
      
      // Simulate file drop
      onDropCallback!([mockFile])

      await waitFor(() => {
        expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
      })
    })
  })

  describe('File Validation', () => {
    test('accepts valid file types', () => {
      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      render(<DocumentUpload />)
      
      const callArgs = mockUseDropzone.mock.calls[0][0]
      expect(callArgs.accept).toEqual({
        'application/pdf': ['.pdf'],
        'text/markdown': ['.md'],
        'text/plain': ['.txt'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      })
    })

    test('validates file size limits', async () => {
      // Create a large file that exceeds 50MB limit
      const mockLargeFile = new File(['x'.repeat(100 * 1024 * 1024)], 'large.pdf', { 
        type: 'application/pdf' 
      })
      
      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      let onDropCallback: (files: File[]) => void
      mockUseDropzone.mockImplementation(({ onDrop }: { onDrop: (files: File[]) => void }) => {
        onDropCallback = onDrop
        return {
          getRootProps: () => ({ 'data-testid': 'dropzone' }),
          getInputProps: () => ({ 'data-testid': 'file-input' }),
          isDragActive: false,
        }
      })

      render(<DocumentUpload />)
      
      // Wait for initial loading to complete
      await waitFor(() => {
        expect(screen.queryByText('Loading documents...')).not.toBeInTheDocument()
      })
      
      // Simulate dropping large file
      await act(async () => {
        onDropCallback!([mockLargeFile])
      })

      await waitFor(() => {
        expect(screen.getByText(/too large/i)).toBeInTheDocument()
      })
    })

    test('handles multiple file uploads', async () => {
      const mockFiles = [
        new File(['test 1'], 'test1.pdf', { type: 'application/pdf' }),
        new File(['test 2'], 'test2.pdf', { type: 'application/pdf' }),
      ]
      
      mockDesktopAPI.uploadDocument.mockResolvedValue({
        id: '2',
        filename: 'test.pdf',
        status: 'uploaded',
      })

      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      let onDropCallback: (files: File[]) => void
      mockUseDropzone.mockImplementation(({ onDrop }: { onDrop: (files: File[]) => void }) => {
        onDropCallback = onDrop
        return {
          getRootProps: () => ({ 'data-testid': 'dropzone' }),
          getInputProps: () => ({ 'data-testid': 'file-input' }),
          isDragActive: false,
        }
      })

      render(<DocumentUpload />)
      
      // Simulate multiple file drop
      onDropCallback!(mockFiles)

      await waitFor(() => {
        expect(mockDesktopAPI.uploadDocument).toHaveBeenCalledTimes(2)
      })
    })
  })

  describe('Document Management', () => {
    test('loads and displays documents on mount', async () => {
      mockDesktopAPI.getDocuments.mockResolvedValue({
        documents: [
          {
            id: '1',
            filename: 'test-doc.pdf',
            title: 'Test Document',
            file_size: 1024000,
            upload_date: '2025-01-03T10:00:00Z',
            processing_status: 'completed',
          },
          {
            id: '2',
            filename: 'another-doc.pdf',
            title: 'Another Document',
            file_size: 2048000,
            upload_date: '2025-01-03T11:00:00Z',
            processing_status: 'processing',
          },
        ],
      })

      render(<DocumentUpload />)
      
      await waitFor(() => {
        expect(screen.queryByText('Loading documents...')).not.toBeInTheDocument()
      })
      
      await waitFor(() => {
        expect(screen.getByText('Test Document')).toBeInTheDocument()
        expect(screen.getByText('Another Document')).toBeInTheDocument()
        expect(screen.getByText('1.0 MB')).toBeInTheDocument()
        expect(screen.getByText('2.0 MB')).toBeInTheDocument()
      })
    })

    test('handles document deletion', async () => {
      mockDesktopAPI.deleteDocument.mockResolvedValue({ success: true })

      render(<DocumentUpload />)
      
      await waitFor(() => {
        expect(screen.getByText('Test Document')).toBeInTheDocument()
      })

      const deleteButton = screen.getByRole('button', { name: /delete test document/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        expect(mockDesktopAPI.deleteDocument).toHaveBeenCalledWith('1')
      })
    })

    test('displays processing status correctly', async () => {
      mockDesktopAPI.getDocuments.mockResolvedValue({
        documents: [
          {
            id: '1',
            filename: 'processing-doc.pdf',
            title: 'Processing Document',
            file_size: 1024000,
            upload_date: '2025-01-03T10:00:00Z',
            processing_status: 'processing',
          },
          {
            id: '2',
            filename: 'error-doc.pdf',
            title: 'Error Document',
            file_size: 1024000,
            upload_date: '2025-01-03T10:00:00Z',
            processing_status: 'error',
          },
        ],
      })

      render(<DocumentUpload />)
      
      await waitFor(() => {
        expect(screen.queryByText('Loading documents...')).not.toBeInTheDocument()
      })
      
      await waitFor(() => {
        expect(screen.getByText('Processing Document')).toBeInTheDocument()
        expect(screen.getByText('Error Document')).toBeInTheDocument()
        // Check for status indicators in the document details
        expect(screen.getByText(/Processing/)).toBeInTheDocument()
        expect(screen.getByText(/Error/)).toBeInTheDocument()
      })
    })
  })

  describe('Utility Functions', () => {
    test('formats file sizes correctly', () => {
      render(<DocumentUpload />)
      
      // Test various file sizes through component rendering
      const testCases = [
        { bytes: 0, expected: '0 Bytes' },
        { bytes: 1024, expected: '1.0 kB' },
        { bytes: 1048576, expected: '1.0 MB' },
        { bytes: 1073741824, expected: '1.0 GB' },
      ]

      // This would be tested through the actual document rendering
      // The formatFileSize function would be extracted as a utility
    })
  })

  describe('Error Handling', () => {
    test('displays error when document loading fails', async () => {
      mockDesktopAPI.getDocuments.mockRejectedValue(new Error('Network error'))

      render(<DocumentUpload />)
      
      await waitFor(() => {
        expect(screen.getByText(/error loading documents/i)).toBeInTheDocument()
      })
    })

    test('handles API errors gracefully', async () => {
      const mockFile = new File(['test'], 'test.pdf', { type: 'application/pdf' })
      mockDesktopAPI.uploadDocument.mockRejectedValue({
        response: { status: 413, statusText: 'Payload Too Large' }
      })

      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      let onDropCallback: (files: File[]) => void
      mockUseDropzone.mockImplementation(({ onDrop }: { onDrop: (files: File[]) => void }) => {
        onDropCallback = onDrop
        return {
          getRootProps: () => ({ 'data-testid': 'dropzone' }),
          getInputProps: () => ({ 'data-testid': 'file-input' }),
          isDragActive: false,
        }
      })

      render(<DocumentUpload />)
      
      onDropCallback!([mockFile])

      await waitFor(() => {
        expect(screen.getByText(/file too large/i)).toBeInTheDocument()
      })
    })
  })

  describe('Drag and Drop States', () => {
    test('shows active drag state', () => {
      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      mockUseDropzone.mockReturnValue({
        getRootProps: () => ({ 'data-testid': 'dropzone' }),
        getInputProps: () => ({ 'data-testid': 'file-input' }),
        isDragActive: true,
      })

      render(<DocumentUpload />)
      
      const dropzone = screen.getByTestId('dropzone')
      expect(dropzone).toHaveClass('border-primary', 'bg-primary/5')
    })

    test('shows default drag state', () => {
      const { useDropzone } = require('react-dropzone')
      const mockUseDropzone = useDropzone as jest.Mock
      
      mockUseDropzone.mockReturnValue({
        getRootProps: () => ({ 'data-testid': 'dropzone' }),
        getInputProps: () => ({ 'data-testid': 'file-input' }),
        isDragActive: false,
      })

      render(<DocumentUpload />)
      
      const dropzone = screen.getByTestId('dropzone')
      expect(dropzone).toHaveClass('border-border', 'hover:border-primary/50')
    })
  })
})