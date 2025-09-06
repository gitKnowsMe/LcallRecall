# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalRecall is a cross-platform desktop RAG (Retrieval-Augmented Generation) application built with Electron + Next.js frontend and FastAPI backend. It provides private, local document processing and AI-powered question answering using the Phi-2 model.

### Architecture Overview

**Hybrid Desktop Application:**
- **Frontend**: Next.js React app with TypeScript, Tailwind CSS, and Radix UI components
- **Backend**: FastAPI Python server with SQLite databases and FAISS vector storage  
- **Desktop Shell**: Electron wrapper with IPC communication bridge
- **Local AI**: Phi-2 GGUF model via llama-cpp-python (singleton pattern)
- **Vector DB**: Workspace-based FAISS indices with sentence-transformers embeddings

**Key Architectural Patterns:**
- **Service-Oriented**: Centralized service manager with dependency injection
- **Workspace Isolation**: Per-user workspaces prevent data cross-contamination
- **Streaming Support**: Server-Sent Events for real-time AI responses
- **TDD Approach**: Comprehensive test coverage (425+ tests across backend/frontend)

## Development Commands

### Backend Development
```bash
# Install Python dependencies
cd backend && pip install -r requirements.txt

# Run backend tests
cd backend && python -m pytest tests/unit/ -v
cd backend && python -m pytest tests/integration/ -v

# Run specific test file
cd backend && python -m pytest tests/unit/test_model_manager.py -v

# Start backend development server
cd backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run backend with async mode
cd backend && python -m pytest --asyncio-mode=auto
```

### Frontend Development
```bash
# Install frontend dependencies  
cd app && npm install

# Run frontend tests
cd app && npm test
cd app && npm run test:watch
cd app && npm run test:coverage

# Start frontend development server
cd app && npm run dev

# Build frontend for production
cd app && npm run build
```

### Desktop Application Development
```bash
# Install all dependencies
npm install

# Start full development environment (backend + frontend + electron)
npm run dev

# Start just electron with existing frontend
npm run electron:dev

# Build desktop application
npm run build

# Create distribution packages
npm run dist
```

## Critical Configuration

### Model Configuration
The application requires the Phi-2 GGUF model at:
`/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf`

Update `backend/app/services/llm_service.py` if model path changes.

### Database Architecture
- **Authentication DB**: `backend/data/auth.db` - Encrypted user credentials
- **Metadata DB**: `backend/data/global_metadata.db` - Document metadata
- **Workspace Indices**: `backend/data/workspaces/` - Per-workspace FAISS vector stores

### Security Architecture
- JWT token-based authentication with bcrypt password hashing
- Workspace isolation prevents cross-user data access
- Context isolation in Electron with secure IPC bridge
- Local-only operation (no external API calls)

## Core Services Architecture

**Backend Service Stack:**
- `ServiceManager`: Centralized dependency injection and service orchestration
- `ModelManager`: Singleton Phi-2 model loading and text generation (saves 2-4GB RAM)
- `VectorStoreManager`: Workspace-based FAISS indices with embedding generation
- `AuthService`: JWT authentication with workspace management
- `DocumentProcessor`: PDF processing with semantic chunking via spaCy
- `QueryService`: RAG pipeline with vector search and LLM generation

**Frontend Architecture:**
- React Context API for authentication state management
- Desktop API client with IPC communication to backend
- Component-based UI with comprehensive Jest test coverage
- Real-time streaming via EventSource for AI responses

## Key Integration Points

**Electron ↔ Backend Communication:**
- Backend auto-starts as Python subprocess on Electron launch
- Health monitoring and status indicators
- Secure IPC bridge in `electron/preload.js`

**Frontend ↔ Backend API:**
- Authentication: `/api/auth/*` endpoints
- Documents: `/api/documents/*` with file upload
- Query: `/api/query/*` with streaming support via SSE

**Testing Strategy:**
- Backend: pytest with comprehensive unit/integration tests
- Frontend: Jest + React Testing Library with mocking
- TDD approach with 425+ total tests across the stack

## Common Debugging

**Backend Issues:**
- Check model path in `llm_service.py` 
- Verify FAISS workspace permissions in `data/workspaces/`
- Monitor service health via `/status` endpoint

**Frontend Issues:**
- Test components with `npm test` in `app/` directory
- Check IPC bridge communication in browser dev tools
- Verify authentication context state

**Desktop Integration:**
- Check Electron main process logs
- Verify backend subprocess startup
- Test IPC communication between main/renderer processes

## Model Integration Notes

The application uses a singleton pattern for the Phi-2 model to optimize memory usage. The model loads once at startup and is reused across all requests. If you need to modify model loading, update the ModelManager service and ensure proper async/await patterns are maintained for thread safety.

Document processing uses semantic chunking via spaCy to preserve context across chunk boundaries. Vector embeddings use sentence-transformers/all-MiniLM-L6-v2 with 384-dimensional vectors stored in workspace-specific FAISS indices.