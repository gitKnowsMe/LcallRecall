"use client"

import { useState, useCallback, useEffect } from "react"
import { useDropzone } from "react-dropzone"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Upload, FileText, X, AlertCircle, CheckCircle, Clock } from "lucide-react"
import { desktopAPI } from "@/lib/desktop-api"

interface Document {
  id: string
  filename: string
  title?: string
  file_size: number
  upload_date: string
  processing_status: "uploading" | "processing" | "completed" | "error"
}

interface UploadingFile {
  id: string
  file: File
  progress: number
  status: "uploading" | "error"
  error?: string
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
  'text/markdown': ['.md'],
  'text/plain': ['.txt'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}

export function DocumentUpload() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const validFiles = acceptedFiles.filter(file => {
      // File size validation
      if (file.size > MAX_FILE_SIZE) {
        setError(`File "${file.name}" is too large. Maximum size is 50MB.`)
        return false
      }
      return true
    })

    if (validFiles.length === 0) return

    // Create uploading entries
    const newUploadingFiles: UploadingFile[] = validFiles.map(file => ({
      id: `uploading-${Date.now()}-${Math.random()}`,
      file,
      progress: 0,
      status: 'uploading' as const,
    }))

    setUploadingFiles(prev => [...prev, ...newUploadingFiles])
    setError(null)

    // Upload files
    for (const uploadingFile of newUploadingFiles) {
      try {
        const result = await desktopAPI.uploadDocument(uploadingFile.file)
        
        // Remove from uploading
        setUploadingFiles(prev => prev.filter(f => f.id !== uploadingFile.id))
        
        // Refresh documents list
        await loadDocuments()
      } catch (error: any) {
        console.error('Upload failed:', error)
        
        // Update uploading file with error
        setUploadingFiles(prev => prev.map(f => 
          f.id === uploadingFile.id 
            ? { ...f, status: 'error' as const, error: getErrorMessage(error) }
            : f
        ))
      }
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    multiple: true,
    maxSize: MAX_FILE_SIZE,
  })

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "kB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  // Load documents from backend
  const loadDocuments = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await desktopAPI.getDocuments()
      setDocuments(response.documents || [])
    } catch (error: any) {
      console.error('Failed to load documents:', error)
      setError('Error loading documents. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Load documents on mount
  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  const handleDeleteDocument = async (docId: string) => {
    try {
      await desktopAPI.deleteDocument(docId)
      setDocuments((prev) => prev.filter((doc) => doc.id !== docId))
    } catch (error: any) {
      console.error('Failed to delete document:', error)
      setError('Failed to delete document. Please try again.')
    }
  }

  const getErrorMessage = (error: any): string => {
    if (error.response?.status === 413) {
      return 'File too large'
    }
    return error.message || 'Upload failed'
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'processing':
        return <Clock className="h-4 w-4 text-yellow-500" />
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      default:
        return <FileText className="h-4 w-4 text-primary" />
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString()
    } catch {
      return dateString
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      <div className="flex items-center justify-between p-6 border-b border-border">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Upload</h1>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-6">
        <div>
          <h2 className="text-lg font-medium text-foreground mb-2">Upload Documents</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Upload PDFs, Markdown files, text documents, and more to expand your knowledge base.
          </p>

          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
              isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <div className="space-y-2">
              <p className="text-lg font-medium text-foreground">Drop files here or click to browse</p>
              <p className="text-sm text-muted-foreground">Supports PDF, Markdown, TXT, DOCX, and more</p>
            </div>
            <Button className="mt-4">Browse Files</Button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
            <p className="text-red-700">{error}</p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setError(null)}
              className="ml-auto h-6 w-6 p-0 text-red-500 hover:text-red-700"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Uploading Files */}
        {uploadingFiles.length > 0 && (
          <div>
            <h3 className="text-md font-medium text-foreground mb-2">Uploading</h3>
            <Card className="bg-card">
              <CardContent className="p-0">
                <div className="space-y-0">
                  {uploadingFiles.map((uploadingFile, index) => (
                    <div
                      key={uploadingFile.id}
                      className={`flex items-center justify-between p-4 ${
                        index !== uploadingFiles.length - 1 ? "border-b border-border" : "
                      }`}
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <div className="p-2 bg-primary/20 rounded">
                          {uploadingFile.status === 'error' ? (
                            <AlertCircle className="h-4 w-4 text-red-500" />
                          ) : (
                            <Clock className="h-4 w-4 text-yellow-500 animate-pulse" />
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="font-medium text-foreground">{uploadingFile.file.name}</div>
                          <div className="text-sm text-muted-foreground">
                            {formatFileSize(uploadingFile.file.size)} • 
                            {uploadingFile.status === 'uploading' && ' Uploading...'}
                            {uploadingFile.status === 'error' && ` ${uploadingFile.error || 'Upload failed'}`}
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setUploadingFiles(prev => prev.filter(f => f.id !== uploadingFile.id))}
                        className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <div>
          <h2 className="text-lg font-medium text-foreground mb-4">Document Library</h2>

          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading documents...</p>
            </div>
          ) : (
            <Card className="bg-card">
              <CardContent className="p-0">
                {documents.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No documents uploaded yet.
                  </div>
                ) : (
                  <div className="space-y-0">
                    {documents.map((doc, index) => (
                      <div
                        key={doc.id}
                        className={`flex items-center justify-between p-4 hover:bg-muted/50 transition-colors ${
                          index !== documents.length - 1 ? "border-b border-border" : "
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-primary/20 rounded">
                            {getStatusIcon(doc.processing_status)}
                          </div>
                          <div>
                            <div className="font-medium text-foreground">{doc.title || doc.filename}</div>
                            <div className="text-sm text-muted-foreground">
                              {formatFileSize(doc.file_size)} • {formatDate(doc.created_at)}
                              {doc.processing_status === 'processing' && ' • Processing'}
                              {doc.processing_status === 'error' && ' • Error'}
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteDocument(doc.id)}
                          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                          aria-label={`Delete ${doc.title || doc.filename}`}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
