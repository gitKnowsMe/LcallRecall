import os
import logging
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from ..models.user import User, Base as UserBase
from ..models.document import Document, DocumentChunk, Base as DocumentBase

logger = logging.getLogger(__name__)

# Database paths
AUTH_DB_PATH = "data/auth.db"
GLOBAL_METADATA_DB_PATH = "data/global_metadata.db"

# Create engines
auth_engine = None
metadata_engine = None

# Session makers
AuthSessionLocal = None
MetadataSessionLocal = None

async def init_databases():
    """Initialize SQLite databases"""
    global auth_engine, metadata_engine, AuthSessionLocal, MetadataSessionLocal
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Authentication database
    logger.info("Initializing authentication database...")
    auth_engine = create_engine(
        f"sqlite:///{AUTH_DB_PATH}",
        connect_args={"check_same_thread": False}
    )
    AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)
    
    # Create auth tables
    UserBase.metadata.create_all(bind=auth_engine)
    
    # Global metadata database
    logger.info("Initializing global metadata database...")
    metadata_engine = create_engine(
        f"sqlite:///{GLOBAL_METADATA_DB_PATH}",
        connect_args={"check_same_thread": False}
    )
    MetadataSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=metadata_engine)
    
    # Create metadata tables
    DocumentBase.metadata.create_all(bind=metadata_engine)
    
    logger.info("✅ Databases initialized successfully")

def get_auth_db() -> Session:
    """Get authentication database session"""
    if AuthSessionLocal is None:
        raise RuntimeError("Auth database not initialized")
    
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_metadata_db() -> Session:
    """Get metadata database session"""
    if MetadataSessionLocal is None:
        raise RuntimeError("Metadata database not initialized")
    
    db = MetadataSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Database utilities
def get_next_workspace_id() -> int:
    """Get next available workspace ID"""
    if AuthSessionLocal is None:
        return 1
    
    db = next(get_auth_db())
    try:
        max_workspace = db.query(User.workspace_id).order_by(User.workspace_id.desc()).first()
        if max_workspace:
            return max_workspace[0] + 1
        return 1
    finally:
        db.close()

def workspace_exists(workspace_id: int) -> bool:
    """Check if workspace exists"""
    workspace_dir = f"data/workspaces/workspace_{workspace_id:03d}"
    return os.path.exists(workspace_dir)

async def cleanup_databases():
    """Cleanup database connections"""
    global auth_engine, metadata_engine
    
    if auth_engine:
        auth_engine.dispose()
    if metadata_engine:
        metadata_engine.dispose()
    
    logger.info("Database connections closed")