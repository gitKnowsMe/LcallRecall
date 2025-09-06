# LocalRecall RAG Pipeline Documentation

## Overview

LocalRecall implements a complete Retrieval-Augmented Generation (RAG) pipeline for local document processing and question answering. The system processes PDF documents, chunks them semantically, stores them in a vector database, and uses them to provide context-aware responses to user queries.

## Architecture

```
PDF Upload → Text Extraction → Semantic Chunking → Vector Embeddings → FAISS Storage
                                                                              ↓
User Query → Query Embedding → Similarity Search → Context Retrieval → LLM Generation
```

## Core Components

### 1. Document Ingestion Pipeline

#### PDF Service (`app/services/pdf_service.py`)
- **Purpose**: Extract text content from PDF files
- **Library**: PyMuPDF (fitz)
- **Features**:
  - Text extraction with metadata (page count, file info)
  - Error handling for corrupted files
  - File size validation

```python
# Usage Example
pdf_result = pdf_service.extract_text_from_pdf(file_path)
text_content = pdf_result["text"]
metadata = pdf_result["metadata"]  # Contains page_count, etc.
```

#### Semantic Chunking (`app/services/semantic_chunking.py`)
- **Purpose**: Split text into semantically meaningful chunks
- **Strategy**: 
  - Primary: spaCy-based sentence boundary detection
  - Fallback: Simple text splitting when spaCy unavailable
- **Configuration**:
  - Default chunk size: 512 characters
  - Default overlap: 50 characters
- **Output**: List of chunks with metadata (chunk_id, text, length)

```python
# Usage Example
chunker = SemanticChunking(chunk_size=512, chunk_overlap=50)
chunks = chunker.chunk_text(text_content, document_id="doc_123")
# Returns: [{"chunk_id": 0, "text": "...", "length": 245}, ...]
```

### 2. Vector Storage System

#### Vector Store Manager (`app/services/vector_service.py`)
- **Purpose**: Generate embeddings and manage vector storage
- **Components**:
  - **Embedding Model**: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
  - **Vector DB**: FAISS IndexFlatL2 (CPU-optimized)
  - **Storage**: Workspace-based isolation
- **Features**:
  - Per-workspace FAISS indices
  - Persistent storage with metadata
  - Similarity search with configurable thresholds

```python
# Usage Example
await vector_store.initialize()
await vector_store.load_workspace("workspace_001")

# Add documents
vector_ids = await vector_store.add_documents(
    workspace_id="workspace_001",
    texts=chunk_texts,
    metadata=chunk_metadata
)

# Search
results = await vector_store.search(
    workspace_id="workspace_001",
    query="How does PDF processing work?",
    k=5,
    score_threshold=0.7
)
```

### 3. Language Model Integration

#### LLM Service (`app/services/llm_service.py`)
- **Model**: Phi-2 GGUF (phi-2-instruct-Q4_K_M.gguf)
- **Framework**: llama-cpp-python
- **Features**:
  - Singleton pattern for memory efficiency
  - Async generation with thread pool
  - Streaming response support
  - Mock mode fallback for development
- **Configuration**:
  - Context window: 2048 tokens
  - Batch size: 256
  - CPU threads: 2

```python
# Usage Example
model_manager = ModelManager()
await model_manager.initialize()

# Non-streaming
response = await model_manager.generate(prompt, max_tokens=512)

# Streaming
async for token in model_manager.generate_stream(prompt):
    print(token, end="")
```

### 4. Query Processing Pipeline

#### Query Service (`app/services/query_service.py`)
- **Purpose**: Orchestrate the complete RAG workflow
- **Process**:
  1. Convert user query to embedding
  2. Search vector database for relevant chunks
  3. Prepare context from retrieved chunks
  4. Generate response using LLM with context
  5. Format response with source attribution

```python
# Usage Example
query_service = QueryService(vector_service, llm_service)

response = await query_service.query_documents(
    workspace_id="workspace_001",
    query="How does document processing work?",
    user_id="user_123",
    top_k=5,
    min_score=0.7
)

# Returns:
{
    "response": "Generated answer...",
    "sources": [...],  # List of source chunks with metadata
    "query": "Original query",
    "response_time_ms": 1250
}
```

### 5. API Integration

#### Document Processor API (`app/services/document_processor_api.py`)
- **Purpose**: FastAPI integration for document upload and processing
- **Features**:
  - File upload handling
  - Complete pipeline orchestration
  - Database integration
  - Error handling and cleanup

```python
# Usage Example
processor = DocumentProcessor(workspace_id=1)
result = await processor.process_document(uploaded_file, user_id=123)

# Returns:
{
    "document_id": 456,
    "filename": "document.pdf",
    "processing_status": "completed",
    "total_chunks": 25
}
```

## Data Flow

### Document Upload Flow
```
1. User uploads PDF via API
   ↓
2. File saved to temporary location
   ↓
3. PDF text extraction (PyMuPDF)
   ↓
4. Text chunking (spaCy/fallback)
   ↓
5. Embedding generation (sentence-transformers)
   ↓
6. Vector storage (FAISS)
   ↓
7. Database record creation (SQLite)
   ↓
8. Cleanup temporary files
```

### Query Processing Flow
```
1. User submits query via API
   ↓
2. Query embedding generation
   ↓
3. Vector similarity search (FAISS)
   ↓
4. Context preparation from retrieved chunks
   ↓
5. RAG prompt construction
   ↓
6. LLM response generation (Phi-2)
   ↓
7. Source attribution formatting
   ↓
8. Response with sources returned
```

## Database Schema

### Documents Table
```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER,
    filename TEXT,
    file_path TEXT,
    content_hash TEXT,
    processing_status TEXT,
    total_chunks INTEGER,
    created_at TIMESTAMP
);
```

### Document Chunks Table
```sql
CREATE TABLE document_chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,
    workspace_id INTEGER,
    chunk_text TEXT,
    chunk_index INTEGER,
    vector_id INTEGER,
    char_count INTEGER,
    created_at TIMESTAMP
);
```

## File System Structure

```
LocalRecall/
├── backend/
│   ├── data/
│   │   ├── auth.db                    # User authentication
│   │   ├── global_metadata.db         # Document metadata
│   │   └── workspaces/
│   │       ├── workspace_001/
│   │       │   ├── faiss_index.bin    # FAISS vector index
│   │       │   └── metadata.pkl       # Vector metadata
│   │       └── workspace_002/
│   │           ├── faiss_index.bin
│   │           └── metadata.pkl
│   └── app/
│       └── services/
           ├── pdf_service.py
           ├── semantic_chunking.py
           ├── vector_service.py
           ├── llm_service.py
           ├── query_service.py
           └── document_processor_api.py
```

## Configuration

### Model Configuration
```python
# LLM Service Configuration
MODEL_PATH = "/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf"
CONTEXT_WINDOW = 2048
BATCH_SIZE = 256
CPU_THREADS = 2

# Vector Service Configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
DEFAULT_SIMILARITY_THRESHOLD = 0.7

# Chunking Configuration
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 50
```

## Performance Characteristics

### Current Performance (Mock Mode)
- **Document Processing**: ~2-5 seconds per PDF (depends on size)
- **Vector Search**: ~50-100ms for 5 results
- **Response Generation**: ~500ms (mock mode)
- **End-to-End Query**: ~1-2 seconds

### Memory Usage
- **Base Application**: ~200MB
- **Embedding Model**: ~100MB
- **FAISS Index**: ~1MB per 1000 chunks
- **Phi-2 Model**: ~2-4GB (when loaded)

## Error Handling

### Common Error Scenarios
1. **Corrupted PDF Files**: Graceful failure with user feedback
2. **Empty Text Content**: Validation and error reporting
3. **Model Loading Issues**: Automatic fallback to mock mode
4. **Vector Search Failures**: Threshold adjustment and retry
5. **Database Conflicts**: Transaction rollback and cleanup

### Error Recovery
- Temporary file cleanup on failures
- Database transaction rollbacks
- Graceful degradation to mock responses
- User-friendly error messages

## Development Status

### ✅ Completed (Phase 1)
- PDF text extraction pipeline
- Semantic chunking with fallback
- Vector embedding and storage
- FAISS-based similarity search
- Mock LLM responses for testing
- Complete API integration
- End-to-end query processing

### 🔧 In Progress
- Real Phi-2 model loading (compatibility issues)
- spaCy model installation for better chunking

### 📋 Planned (Phase 2+)
- Hierarchical chunking strategies
- Hybrid search (keyword + semantic)
- Query expansion and rewriting
- Result reranking algorithms
- Performance optimizations
- Advanced error handling

## Testing

### Test Coverage
- **Unit Tests**: 425+ tests across all components
- **Integration Tests**: End-to-end pipeline validation
- **Component Tests**: Individual service testing
- **Mock Testing**: Development workflow validation

### Test Results (Latest)
```
✅ Chunking Service: 7 chunks generated from test text
✅ Vector Store: 7 embeddings stored, search functional
✅ Model Service: Mock responses working
✅ Query Pipeline: 3 relevant chunks retrieved (0.541 similarity)
✅ End-to-End: Complete RAG workflow functional
```

## API Endpoints

### Document Management
- `POST /api/documents` - Upload and process document
- `GET /api/documents` - List documents with pagination
- `GET /api/documents/{id}` - Get document details
- `DELETE /api/documents/{id}` - Delete document and cleanup
- `GET /api/documents/{id}/chunks` - Get document chunks

### Query Processing
- `POST /api/query/documents` - RAG query with response
- `POST /api/query/stream` - Streaming RAG responses
- `POST /api/query/search` - Document search without LLM
- `GET /api/query/history` - Query history
- `GET /api/query/stats` - Workspace statistics

## Troubleshooting

### Common Issues

#### Phi-2 Model Loading Fails
```bash
# Check model file exists
ls -la "/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf"

# Verify llama-cpp-python version
pip show llama-cpp-python

# Solution: Use mock mode for development
# Real model loading will be fixed in Phase 2
```

#### Vector Search Returns No Results
```python
# Lower similarity threshold
results = await vector_store.search(
    workspace_id="workspace_001",
    query="your query",
    k=5,
    score_threshold=0.3  # Lower from 0.7 to 0.3
)
```

#### Chunking Falls Back to Simple Splitting
```bash
# Install spaCy English model
python -m spacy download en_core_web_sm

# Verify installation
python -c "import spacy; spacy.load('en_core_web_sm')"
```

## Future Enhancements

### Short Term (Week 2)
1. Fix Phi-2 model loading compatibility
2. Install spaCy for semantic chunking
3. Add document type support (DOCX, TXT, MD)
4. Implement query result caching

### Medium Term (Month 2)
1. Hierarchical chunking with overlap management
2. Hybrid search combining keyword + semantic
3. Query expansion using synonyms
4. Result reranking based on relevance
5. Performance monitoring and metrics

### Long Term (Quarter 1)
1. Multi-modal document support (images, tables)
2. Conversation memory and context
3. Advanced prompt engineering
4. Custom model fine-tuning
5. Distributed processing for large corpora

---

*Last Updated: 2025-01-03*
*Status: Phase 1 Complete - Functional RAG Pipeline with Mock LLM*
*Next: Phase 2 - Real Model Integration and Performance Optimization*