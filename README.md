# LocalRecall

**Private, Local RAG Desktop Application**

LocalRecall is a desktop application that provides document ingestion, semantic search, and AI-powered question answering using local models. Your data never leaves your machine.

## Features

- 🔒 **100% Private** - All processing happens locally
- 📚 **Document Processing** - Upload and process PDFs with semantic chunking
- 🤖 **AI Chat** - Ask questions about your documents using Phi-2 model
- 🔍 **Vector Search** - Fast semantic search across all documents
- 🏠 **Workspace Isolation** - Organize documents in separate workspaces
- ⚡ **Streaming Responses** - Real-time AI responses
- 🖥️ **Cross-Platform** - Available for Mac, Windows, and Linux

## Technology Stack

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components

### Backend
- **FastAPI** - Python web framework
- **Phi-2** - Local language model (GGUF format)
- **FAISS** - Vector database for semantic search
- **SQLite** - Document metadata storage
- **spaCy** - Semantic text chunking

### Desktop
- **Electron** - Cross-platform desktop framework
- **IPC** - Secure communication between processes

## Prerequisites

Before running LocalRecall, ensure you have:

1. **Node.js** (v18 or higher)
2. **Python** (3.11 or higher)
3. **Phi-2 Model**: Download `phi-2-instruct-Q4_K_M.gguf` model file
4. **System Requirements**: 8GB+ RAM recommended

## Quick Start

### 1. Install Dependencies

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies  
npm run backend:install
```

### 2. Configure Model Path

Update the model path in `backend/app/main.py`:

```python
"model": {
    "path": "/path/to/your/phi-2-instruct-Q4_K_M.gguf",
    # ...
}
```

### 3. Development Mode

```bash
# Start both backend and frontend in development
npm run dev
```

This will:
- Start the FastAPI backend on `http://localhost:8000`
- Start the Next.js frontend on `http://localhost:3000`
- Launch the Electron desktop app

### 4. Production Build

```bash
# Build for production
npm run build

# Create distribution packages
npm run dist
```

## Project Structure

```
LocalRecall/
├── electron/           # Electron main process
│   ├── main.js        # App entry point
│   ├── preload.js     # Secure IPC bridge
│   └── menu.js        # Application menu
├── app/               # Frontend (Next.js)
│   ├── app/          # Next.js pages
│   ├── components/   # React components
│   └── package.json  # Frontend dependencies
├── backend/          # Python FastAPI backend
│   ├── app/         # Application code
│   ├── tests/       # Test suite (425+ tests)
│   └── requirements.txt
├── resources/       # App icons and assets
├── scripts/        # Build scripts
└── package.json    # Electron configuration
```

## Development

### Available Scripts

```bash
# Development
npm run dev                 # Start full development environment
npm run frontend:dev        # Frontend only
npm run backend:dev         # Backend only
npm run electron:dev        # Electron + frontend

# Building
npm run build              # Build for production
npm run frontend:build     # Build frontend
npm run electron:pack      # Package Electron app
npm run electron:dist      # Create distribution

# Testing
cd backend && python -m pytest  # Run backend tests
```

### Backend API

The FastAPI backend provides these endpoints:

- **Authentication**: `/auth/login`, `/auth/register`, `/auth/logout`
- **Documents**: `/documents/upload`, `/documents/`, `/documents/{id}`
- **Query**: `/query/documents`, `/query/stream`, `/query/search`
- **Health**: `/health`, `/status`

API documentation available at: `http://localhost:8000/docs`

## Architecture

### Desktop Integration

LocalRecall integrates three main components:

1. **Electron Main Process**: Manages application lifecycle, windows, and Python backend
2. **Frontend (Renderer)**: Next.js application providing the user interface
3. **Python Backend**: FastAPI server handling AI processing and data management

### Security

- **Process Isolation**: Frontend runs in isolated renderer process
- **IPC Communication**: Secure communication via Electron's IPC
- **No External APIs**: All processing happens locally
- **Data Encryption**: User authentication and sensitive data encrypted

### Model Management

- **Singleton Loading**: Phi-2 model loaded once at startup
- **Memory Optimization**: Efficient memory usage for large models
- **Streaming Support**: Real-time response generation

## Configuration

### Model Configuration

Edit `backend/app/main.py` to configure the AI model:

```python
"model": {
    "path": "/Users/you/models/phi-2-instruct-Q4_K_M.gguf",
    "max_context_length": 4096,
    "batch_size": 512
}
```

### Database Configuration

```python
"database": {
    "auth_db_path": "data/auth.db",
    "metadata_db_path": "data/metadata.db"
}
```

## Contributing

LocalRecall is built with Test-Driven Development (TDD):

1. **425+ Tests**: Comprehensive test coverage across all components
2. **Type Safety**: TypeScript frontend, type hints in Python
3. **Code Quality**: Consistent formatting and linting

## License

MIT License - see LICENSE file for details

## Support

- **Documentation**: [CLAUDE.md](./CLAUDE.md) for detailed development notes
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Architecture**: See [FRONTEND_INTEGRATION.txt](./FRONTEND_INTEGRATION.txt) for integration details