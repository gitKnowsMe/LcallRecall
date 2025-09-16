  User Registration Requirements

  Does the user need email to register? Yes, email is required for registration, but there's a discrepancy between the backend schema and frontend form.

  Database Schema (backend/data/auth.db):

  CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username VARCHAR(50) UNIQUE NOT NULL,
      email VARCHAR(100) UNIQUE NOT NULL,        -- EMAIL IS REQUIRED
      password_hash VARCHAR(255) NOT NULL,
      workspace_id VARCHAR(36) NOT NULL,
      is_active BOOLEAN DEFAULT TRUE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  Model vs Implementation Issue:

  - User Model (backend/app/models/user.py:12): Only defines username - no email field
  - Database Schema: Requires both username and email as unique, non-null fields
  - Backend Service (backend/app/services/auth_service.py:30): register_user() only accepts username and password parameters
  - Frontend Form (app/components/auth/auth-form.tsx:204): Collects email, password, and optional username
  - Frontend API (app/lib/desktop-api.ts:204): Sends email, password, username to /auth/register

  Authentication Pipeline Architecture

  1. Database Layer

  - Authentication DB: backend/data/auth.db - stores encrypted user credentials
  - Workspace Isolation: Each user gets a unique workspace_id for data segregation
  - Password Security: bcrypt hashing with salt (backend/app/auth/auth_service.py:57)

  2. Backend Authentication Service

  File: backend/app/auth/auth_service.py

  Registration Flow:
  - Password strength validation (8+ characters)
  - Username uniqueness check
  - bcrypt password hashing with salt
  - Automatic workspace assignment via database_service.get_next_workspace_id()
  - Returns {user_id, username, workspace_id}

  Login Flow:
  - Username/password verification with bcrypt
  - Active user status check
  - JWT token generation (24-hour expiry)
  - Workspace mounting via user_manager.mount_user_workspace()
  - Returns access token + user data

  3. JWT Token Management

  - Secret: Environment variable JWT_SECRET_KEY
  - Algorithm: HS256
  - Expiry: 24 hours (1440 minutes)
  - Storage: Browser localStorage (localrecall_token)
  - Authorization: Bearer token in HTTP headers

  4. Workspace Management

  File: backend/app/auth/user_manager.py

  - Each user gets isolated workspace directory: data/workspaces/workspace_{id:03d}/
  - FAISS vector indices loaded per workspace
  - Session tracking with UUID generation
  - Automatic workspace cleanup on logout

  5. Frontend Authentication

  Components:
  - Auth Form: app/components/auth/auth-form.tsx - Combined login/register UI
  - Auth Context: app/lib/auth-context.tsx - React Context for auth state
  - Desktop API: app/lib/desktop-api.ts - HTTP client with token management

  API Endpoints Used:
  - POST /auth/register - User registration
  - POST /auth/login - User authentication
  - POST /auth/logout - Session termination
  - GET /auth/me - Current user info

  Key Architecture Issues

  1. Schema Mismatch: Database requires email, but backend service doesn't handle it
  2. Model Inconsistency: User model missing email field despite database schema
  3. Frontend Disconnect: UI collects email but backend registration may not process it correctly