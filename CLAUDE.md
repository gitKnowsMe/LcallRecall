# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalRecall is a cross-platform desktop RAG (Retrieval-Augmented Generation) application built with Electron + Next.js frontend and FastAPI backend. It provides private, local document processing and AI-powered question answering using the Phi-2 model.

### Architecture Overview

**Hybrid Desktop Application:**
- **Frontend**: Next.js 14 React app with TypeScript, Tailwind CSS v4, and Radix UI components
- **Backend**: FastAPI Python server with SQLite databases and FAISS vector storage  
- **Desktop Shell**: Electron wrapper with IPC communication bridge
- **Local AI**: Phi-2 GGUF model via llama-cpp-python (singleton pattern)
- **Vector DB**: Workspace-based FAISS indices with sentence-transformers embeddings

**Key Architectural Patterns:**
- **Service-Oriented**: Centralized service manager with dependency injection
- **Workspace Isolation**: Per-user workspaces prevent data cross-contamination
- **Streaming Support**: Server-Sent Events for real-time AI responses
- **TDD Approach**: Comprehensive test coverage (425+ tests across backend/frontend)
- **Component-Based**: React components with shadcn/ui design system
- **Core Managers**: ConfigManager, DatabaseManager, ServiceManager for centralized control

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

# Run with coverage report
cd backend && python -m pytest tests/ --cov=app --cov-report=html

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

# Lint frontend code
cd app && npm run lint

# Build frontend for production
cd app && npm run build

# Start production frontend server
cd app && npm start
```

### Desktop Application Development
```bash
# Install all dependencies (including frontend dependencies via postinstall)
npm install

# Start full development environment (backend + frontend + electron)
npm run dev

# Individual development servers
npm run backend:dev        # Backend only on port 8000
npm run frontend:dev       # Frontend only on port 3000  
npm run electron:dev       # Electron + frontend

# Production builds
npm run frontend:build     # Build Next.js frontend
npm run backend:build      # Bundle backend with PyInstaller
npm run build:production   # Build frontend + backend for production
npm run build              # Build complete application (development)
npm run dist               # Create production DMG distribution

# Electron-specific commands
npm run electron           # Start electron (requires built frontend)
npm run electron:pack      # Package without distribution
npm run electron:dist      # Create platform-specific distributions

# Production deployment scripts
./scripts/build-production.sh   # Complete production build with verification
./scripts/build-backend.sh      # Bundle Python backend standalone
./scripts/test-build.sh         # Verify build artifacts and functionality
```

## Critical Configuration

### Model Configuration
The application requires the Phi-2 GGUF model at:
`/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf`

Update `backend/app/services/llm_service.py` if model path changes.

### Database Architecture
- **Authentication DB**: `backend/data/auth.db` - Username-based user credentials (no email required)
- **Metadata DB**: `backend/data/global_metadata.db` - Document metadata
- **Workspace Indices**: `backend/data/workspaces/` - Per-workspace FAISS vector stores

### Security Architecture
- Username-only authentication system with JWT tokens and bcrypt password hashing
- No email requirement - simplified registration for local desktop application
- Workspace isolation prevents cross-user data access
- Context isolation in Electron with secure IPC bridge
- Local-only operation (no external API calls)

## Core Services Architecture

**Backend Service Stack:**
- `ServiceManager`: Centralized dependency injection and service orchestration (app/core/service_manager.py)
- `ConfigManager`: Application configuration management (app/core/config_manager.py)
- `DatabaseManager`: SQLite database connection management (app/core/database_manager.py)
- `ModelManager`: Singleton Phi-2 model loading and text generation (saves 2-4GB RAM)
- `VectorStoreManager`: Workspace-based FAISS indices with embedding generation
- `AuthService`: Username-based JWT authentication with workspace management (no email)
- `DocumentProcessor`: PDF processing with semantic chunking via spaCy (app/services/document_processor.py)
- `QueryService`: RAG pipeline with vector search and LLM generation (app/services/query_service.py)
- `StreamingService`: Real-time response streaming (app/services/streaming_service.py)

**Frontend Architecture:**
- Next.js 14 with App Router and React Server Components
- TypeScript with strict type checking
- Tailwind CSS v4 with shadcn/ui components (Radix UI primitives)
- React Context API for authentication state management
- Desktop API client with IPC communication to backend (Electron preload)
- Component-based UI with comprehensive Jest test coverage
- Real-time streaming via EventSource for AI responses
- Custom UI components: AI chip icons, sacred geometry branding
- **Dual Chat System**: RAG Chat (QueryInterface) + Direct LLM Chat (LLMChat)

## Key Integration Points

**Electron ↔ Backend Communication:**
- Backend auto-starts as Python subprocess on Electron launch
- Health monitoring and status indicators
- Secure IPC bridge in `electron/preload.js`

**Frontend ↔ Backend API:**
- Authentication: `/api/auth/*` endpoints (username-based, no email required)
- Documents: `/api/documents/*` with file upload
- RAG Query: `/api/query/*` with streaming support via SSE
- **Direct LLM**: `/api/llm/*` with streaming support via SSE (no RAG)

**Testing Strategy:**
- Backend: pytest with comprehensive unit/integration tests (`backend/tests/`)
- Frontend: Jest + React Testing Library with mocking (`app/components/__tests__/`)
- TDD approach with 425+ total tests across the stack
- Async testing support with pytest-asyncio
- Mock implementations for external dependencies

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

### RAG Pipeline Troubleshooting

**"No response received" Errors:**
1. Check backend logs for 500 Internal Server Error
2. Verify LLM service `stop` parameter is `[]` not `None`
3. Ensure model is loaded (check `/status` endpoint)
4. Test individual components: vector search → LLM generation → streaming

**Empty or Truncated Responses:**
1. Check streaming service buffer logic in `streaming_service.py`
2. Verify `max_tokens` parameter (should be 1024 for longer responses)
3. Ensure buffer flushing conditions aren't too restrictive
4. Remove `.strip()` conditions that may block whitespace chunks

**Short Single-Sentence Responses:**
1. Update RAG prompt to include explicit length instruction (5-7 sentences)
2. Increase `max_tokens` from default 512 to 1024
3. Add temperature parameter (0.7) for more natural responses
4. Verify prompt format includes "Let me provide a detailed explanation:"

**Sources Found But No AI Response:**
1. Check streaming service `should_flush` conditions
2. Reduce buffer size to 10 bytes for immediate streaming
3. Add word boundary flushing (`'\n' in chunk or ' ' in chunk`)
4. Remove restrictive `.strip()` filtering on buffer content

## Model Integration Notes

The application uses a singleton pattern for the Phi-2 model to optimize memory usage. The model loads once at startup and is reused across all requests. If you need to modify model loading, update the ModelManager service and ensure proper async/await patterns are maintained for thread safety.

### RAG Prompt Format

The application uses an enhanced instruction format for RAG queries (updated from chat-style format to prevent multi-turn conversations):

```
You are a helpful assistant. Answer the question below using the provided context. Provide a comprehensive, detailed response of 5-7 sentences that thoroughly explains the topic. If the context doesn't contain the answer, say "I cannot find this information in the provided context."

CONTEXT:
{context}

QUESTION: {query}

ANSWER: Let me provide a detailed explanation:
```

**Generation Parameters:**
- **Max Tokens**: 1024 (increased from 512 for longer responses)
- **Temperature**: 0.7 (for more natural, varied responses)
- **Stop Tokens**: `[]` (empty list allows natural generation end without premature truncation)

**Benefits of this format:**
- Prevents multi-turn conversation generation
- Clear section delineation with explicit length guidance
- Handles missing information gracefully
- Generates comprehensive 5-7 sentence responses
- More focused, single-turn responses

### Streaming Response Architecture

The streaming service uses aggressive buffering for real-time response delivery:

**Buffer Configuration:**
- **Buffer Size**: 10 bytes (very small for immediate streaming)
- **Flush Interval**: 0.1 seconds (quick response)
- **Word Boundaries**: Flushes on newlines and spaces for natural breaks
- **Whitespace Handling**: Preserves whitespace chunks (removed `.strip()` filtering)

**Stream Flow:**
1. Vector search finds relevant document chunks
2. RAG prompt generated with context and query
3. LLM generates response via `generate_stream()`
4. Streaming service buffers and flushes tokens via Server-Sent Events
5. Frontend receives real-time chunks and displays progressive response

Document processing uses semantic chunking via spaCy to preserve context across chunk boundaries. Vector embeddings use sentence-transformers/all-MiniLM-L6-v2 with 384-dimensional vectors stored in workspace-specific FAISS indices.

## Direct LLM Chat Module

LocalRecall includes a separate direct LLM chat interface alongside the RAG-based document chat, providing users with both constrained (RAG) and unconstrained (direct) AI conversation modes.

### LLM Chat Architecture

**Complete Separation from RAG:**
- **RAG Chat**: `QueryInterface` → `/api/query/*` → Document search + context injection → Phi-2
- **LLM Chat**: `LLMChat` → `/api/llm/*` → Direct Phi-2 communication (no document search)

**Key Features:**
- Direct access to Phi-2 model without RAG pipeline overhead
- Real-time streaming responses via Server-Sent Events
- Separate chat history storage (`localrecall_llm_chat_history`)
- Distinctive yellow "Direct Phi-2" branding vs blue "Local AI" for RAG
- System prompt formatting for quality responses

### LLM Endpoints

**Core Endpoints:**
- `POST /api/llm/chat` - Direct LLM generation with response metadata
- `GET /api/llm/stream` - Real-time streaming (query params + token auth)  
- `POST /api/llm/stream` - Real-time streaming (JSON body + JWT auth)
- `GET /api/llm/health` - Service health check with model status
- `GET /api/llm/info` - Model information and capabilities

**Quality Control:**
- **System Prompt**: `"You are Phi-2, a helpful AI assistant. Answer the user's question directly and concisely.\n\nUser: {question}\nAssistant:"`
- **Stop Tokens**: `["\n\n\n", "User:", "Human:", "Q:", "Question:", "A:", "Answer:", "Assistant:"]`
- **Parameters**: max_tokens=1024, temperature=0.7 (configurable)

### UI Implementation

**Navigation:**
- LLM menu item in sidebar (Zap icon between Memory and Search)
- Routing handled in `main-app.tsx` with "llm" view type

**Component Structure:**
- `LLMChat` component based on `QueryInterface` but stripped of RAG features
- No document search, sources attribution, or context injection
- Separate localStorage for chat history persistence
- Consistent UI patterns with RAG chat but distinctive branding

### Development Notes

**Adding LLM Functionality:**
- Backend endpoints already exist and are registered
- Frontend component follows same patterns as RAG chat
- Desktop API includes `createLLMStream()` method for EventSource streaming
- Quality improvements include system prompts and stop tokens to prevent hallucinations

**Testing LLM Module:**
- Health check: `curl http://localhost:8000/llm/health`
- Stream test: Use LLM menu in desktop app
- Response quality: System prompts prevent off-topic responses
- Error handling: Proper fallbacks for connection issues

## Development Dependencies

### Python Backend Stack
- **Framework**: FastAPI 0.104.1 + Uvicorn 0.24.0 for ASGI server
- **AI/ML**: llama-cpp-python 0.2.19, sentence-transformers 2.7.0, torch 2.1.0
- **Vector DB**: faiss-cpu 1.7.4 for semantic search
- **Document Processing**: PyMuPDF 1.23.8, spaCy 3.7.2 for semantic chunking
- **Database**: SQLAlchemy 2.0.23 + aiosqlite for async SQLite operations
- **Auth**: bcrypt 4.1.2, python-jose[cryptography] 3.3.0 for JWT tokens
- **Testing**: pytest 7.4.3, pytest-asyncio 0.21.1, pytest-mock 3.12.0, httpx 0.25.2

### Frontend Stack  
- **Framework**: Next.js 14.2.16 with App Router and React 18
- **UI**: Tailwind CSS v4, Radix UI primitives, shadcn/ui components
- **Forms**: react-hook-form 7.60.0 + zod 3.25.67 validation
- **Testing**: Jest 30.1.3, @testing-library/react 16.3.0, @testing-library/jest-dom 6.8.0
- **Icons**: lucide-react 0.454.0 for UI icons
- **Utilities**: class-variance-authority 0.7.1, clsx 2.1.1, tailwind-merge 2.5.5

### Desktop Stack
- **Runtime**: Electron 27.0.0 for cross-platform desktop
- **Build**: electron-builder 24.6.4 for distribution packages
- **Development**: concurrently 8.2.2, wait-on 7.0.1 for multi-process dev

## Key File Locations

### Backend Entry Points
- `backend/app/main.py`: FastAPI application setup and configuration loading
- `backend/app/core/service_manager.py`: Centralized service dependency injection
- `backend/app/services/llm_service.py`: Phi-2 model integration and text generation
- `backend/app/services/query_service.py`: RAG pipeline orchestration

### Frontend Entry Points  
- `app/app/layout.tsx`: Root layout with theme provider and global styles
- `app/components/main-app.tsx`: Main application component with auth routing
- `app/components/auth/auth-form.tsx`: Username-only login/register authentication
- `app/components/query/query-interface.tsx`: RAG chat interface with streaming
- `app/components/llm/llm-chat.tsx`: Direct LLM chat interface (no RAG)

### Desktop Integration
- `electron/main.js`: Electron main process with backend subprocess management
- `electron/preload.js`: Secure IPC bridge between renderer and main processes
- `electron/menu.js`: Application menu configuration

## Component Guidelines

### Backend Services
- All services follow dependency injection pattern via ServiceManager
- Services are singletons initialized at application startup
- Async/await patterns used throughout for non-blocking operations
- Configuration loaded via ConfigManager with environment-specific overrides

### Frontend Components
- Use TypeScript with strict type checking
- Follow shadcn/ui patterns for consistent styling
- Implement proper loading and error states
- Use React Context for global state (auth, theme)
- Include Jest tests in `__tests__/` subdirectories

### UI Patterns
- Tailwind CSS v4 utility classes for styling
- Radix UI primitives for accessible components
- Custom icons: AI chip branding, sacred geometry elements
- Dark mode support via next-themes provider

## Production Deployment

LocalRecall includes a comprehensive production deployment system that transforms the development setup into a professional macOS application users can download and install immediately.

### Production Build Architecture

**Target User Experience:**
- Download LocalRecall.dmg (150-200MB)
- Drag to Applications folder
- Launch → Professional setup wizard appears
- Auto-detect or guide Phi-2 model installation
- Create username-only account
- Ready to use - no dependencies required

### Build Process (3 Phases Complete)

**Phase 1: Backend Bundling** ✅
- PyInstaller creates 191MB standalone executable with all Python dependencies
- Includes PyTorch, FAISS, FastAPI, llama-cpp-python, sentence-transformers
- Self-contained backend eliminates Python installation requirement
- Production paths use macOS user data directory

**Phase 2: Model Detection & Setup Wizard** ✅
- Intelligent Phi-2 model auto-detection in common locations
- Professional 3-step setup wizard (welcome, model setup, completion)
- Electron IPC integration for native file dialogs and model validation
- Setup state management with localStorage persistence
- Download instructions and model validation

**Phase 3: Electron Build Configuration** ✅
- Comprehensive package.json build configuration for DMG distribution
- macOS entitlements for ML libraries, JIT compilation, file system access
- DMG installer configuration with custom background and drag-to-Applications
- Cross-architecture support (Intel x64 + Apple Silicon ARM64)
- Production build scripts with verification and testing

### Key Production Files

**Build Scripts:**
- `scripts/build-production.sh`: Complete production build orchestration
- `scripts/build-backend.sh`: PyInstaller bundling with dependency detection
- `scripts/test-build.sh`: Build verification and artifact testing

**Configuration:**
- `resources/entitlements.mac.plist`: macOS security entitlements for AI models
- `package.json` build section: Electron builder configuration
- `electron/model-manager.js`: Phi-2 auto-detection service

**Setup Wizard:**
- `app/components/setup/setup-wizard.tsx`: Main wizard component
- `app/lib/setup-context.tsx`: First-run state management
- `app/components/setup/*`: Individual wizard steps

### Production Commands

```bash
# Complete production build
npm run dist                    # Build frontend + backend + DMG
./scripts/build-production.sh   # Full build with verification

# Individual build steps
npm run build:production        # Frontend + backend only
npm run backend:build          # Bundle Python backend standalone
npm run frontend:build         # Build React frontend

# Testing and verification
./scripts/test-build.sh        # Verify build artifacts
npm run electron:pack          # Test packaging without DMG
```

### Deployment Status

- **Phase 1-3**: Complete (Backend bundling, Setup wizard, Build configuration)
- **Phase 4-5**: In progress (Complete build process, User experience testing)
- **Distribution**: Ready for DMG creation and testing
- **Code Signing**: Configured but requires Apple Developer certificates

### Build Verification Checklist

✅ Frontend compiles to static files  
✅ Backend bundles to 191MB standalone executable  
✅ Model detection finds existing Phi-2 models  
✅ Setup wizard renders with proper styling  
✅ Electron configuration includes all necessary files  
✅ DMG configuration with proper entitlements  
⏳ Complete end-to-end DMG build  
⏳ Manual testing on clean macOS system  
⏳ All features functional without development dependencies