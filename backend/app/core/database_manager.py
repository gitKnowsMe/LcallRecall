import asyncio
import logging
import sqlite3
import os
import shutil
import time
from typing import Dict, Any, Optional, List, Callable
from contextlib import contextmanager, asynccontextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Database manager error"""
    pass


class MigrationError(DatabaseError):
    """Database migration error"""
    pass


class DatabaseManager:
    """Manages database connections, initialization, and migrations"""
    
    CURRENT_SCHEMA_VERSION = 3
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize database manager
        
        Args:
            config: Database configuration
        """
        if not config:
            raise DatabaseError("Configuration is required")
        
        self._validate_config(config)
        
        self.config = config
        self._connections: Dict[str, sqlite3.Connection] = {}
        self._initialized = False
        self._migration_applied: Dict[str, bool] = {}
        
        # SQLAlchemy session factories
        self._session_makers: Dict[str, async_sessionmaker] = {}
        self._engines: Dict[str, create_async_engine] = {}
        
        logger.info("DatabaseManager initialized")
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate database configuration"""
        if "database" not in config:
            raise DatabaseError("Invalid database configuration: missing 'database' section")
        
        db_config = config["database"]
        
        # Check required paths
        if not db_config.get("auth_db_path"):
            raise DatabaseError("Invalid database configuration: auth_db_path is required")
        
        if not db_config.get("metadata_db_path"):
            raise DatabaseError("Invalid database configuration: metadata_db_path is required")
    
    def create_auth_database(self) -> sqlite3.Connection:
        """Create and configure auth database connection"""
        try:
            db_config = self.config["database"]
            db_path = db_config["auth_db_path"]
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Create connection
            conn = sqlite3.connect(
                db_path,
                timeout=db_config.get("connection_timeout", 30),
                check_same_thread=False
            )
            
            # Configure connection
            self._configure_connection(conn)
            
            # Create tables if needed
            if db_config.get("create_tables", True):
                self._create_auth_tables(conn)
            
            self._connections["auth_db"] = conn
            logger.info(f"Auth database connected: {db_path}")
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create auth database: {e}")
            raise DatabaseError(f"Failed to create auth database: {str(e)}")
    
    def create_metadata_database(self) -> sqlite3.Connection:
        """Create and configure metadata database connection"""
        try:
            db_config = self.config["database"]
            db_path = db_config["metadata_db_path"]
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Create connection
            conn = sqlite3.connect(
                db_path,
                timeout=db_config.get("connection_timeout", 30),
                check_same_thread=False
            )
            
            # Configure connection
            self._configure_connection(conn)
            
            # Create tables if needed
            if db_config.get("create_tables", True):
                self._create_metadata_tables(conn)
            
            self._connections["metadata_db"] = conn
            logger.info(f"Metadata database connected: {db_path}")
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create metadata database: {e}")
            raise DatabaseError(f"Failed to create metadata database: {str(e)}")
    
    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """Configure database connection with optimal settings"""
        try:
            db_config = self.config.get("database", {})
            
            # Enable WAL mode if configured
            if db_config.get("enable_wal", True):
                conn.execute("PRAGMA journal_mode = WAL")
            
            # Set synchronous mode
            conn.execute("PRAGMA synchronous = NORMAL")
            
            # Increase cache size (negative value = KB)
            conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Use memory for temp storage
            conn.execute("PRAGMA temp_store = MEMORY")
            
            conn.commit()
            logger.debug("Database connection configured")
            
        except Exception as e:
            logger.error(f"Failed to configure database connection: {e}")
            raise DatabaseError(f"Failed to configure database connection: {str(e)}")
    
    def _create_auth_tables(self, conn: sqlite3.Connection) -> None:
        """Create authentication database tables"""
        try:
            schemas = self._get_auth_table_schemas()
            
            for table_name, schema in schemas.items():
                conn.execute(schema)
                logger.debug(f"Created auth table: {table_name}")
            
            # Create version table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert current version
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (self.CURRENT_SCHEMA_VERSION,)
            )
            
            conn.commit()
            logger.info("Auth database tables created")
            
        except Exception as e:
            logger.error(f"Failed to create auth tables: {e}")
            raise DatabaseError(f"Failed to create auth tables: {str(e)}")
    
    def _create_metadata_tables(self, conn: sqlite3.Connection) -> None:
        """Create metadata database tables"""
        try:
            schemas = self._get_metadata_table_schemas()
            
            for table_name, schema in schemas.items():
                conn.execute(schema)
                logger.debug(f"Created metadata table: {table_name}")
            
            # Create version table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert current version
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (self.CURRENT_SCHEMA_VERSION,)
            )
            
            conn.commit()
            logger.info("Metadata database tables created")
            
        except Exception as e:
            logger.error(f"Failed to create metadata tables: {e}")
            raise DatabaseError(f"Failed to create metadata tables: {str(e)}")
    
    def _get_auth_table_schemas(self) -> Dict[str, str]:
        """Get auth database table schemas"""
        return {
            "users": """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    workspace_id VARCHAR(36) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "sessions": """
                CREATE TABLE IF NOT EXISTS sessions (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    workspace_id VARCHAR(36) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
        }
    
    def _get_metadata_table_schemas(self) -> Dict[str, str]:
        """Get metadata database table schemas"""
        return {
            "workspaces": """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            "documents": """
                CREATE TABLE IF NOT EXISTS documents (
                    id VARCHAR(36) PRIMARY KEY,
                    workspace_id VARCHAR(36) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    file_path VARCHAR(512) NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash VARCHAR(64) NOT NULL,
                    content_type VARCHAR(100),
                    processing_status VARCHAR(20) DEFAULT 'pending',
                    processed_at TIMESTAMP,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
                )
            """,
            "document_chunks": """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id VARCHAR(36) NOT NULL,
                    workspace_id VARCHAR(36) NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    vector_id INTEGER,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE,
                    UNIQUE (document_id, chunk_index)
                )
            """
        }
    
    def get_connection(self, name: str) -> sqlite3.Connection:
        """
        Get database connection
        
        Args:
            name: Connection name
            
        Returns:
            Database connection
            
        Raises:
            DatabaseError: If connection not found
        """
        if name not in self._connections:
            raise DatabaseError(f"Database connection '{name}' not found")
        
        return self._connections[name]
    
    def get_connection_optional(self, name: str) -> Optional[sqlite3.Connection]:
        """
        Get database connection if it exists
        
        Args:
            name: Connection name
            
        Returns:
            Database connection or None
        """
        return self._connections.get(name)
    
    @asynccontextmanager
    async def get_session(self, db_name: str = "metadata_db"):
        """
        Get SQLAlchemy async session context manager
        
        Args:
            db_name: Database name ("auth_db" or "metadata_db")
            
        Yields:
            AsyncSession: SQLAlchemy async session
        """
        if not self._initialized:
            raise DatabaseError("Database manager not initialized")
            
        if db_name not in self._session_makers:
            raise DatabaseError(f"Session maker not found for database: {db_name}")
            
        session_maker = self._session_makers[db_name]
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def initialize_all_databases(self) -> None:
        """Initialize all database connections"""
        if self._initialized:
            logger.warning("Databases already initialized")
            return
        
        try:
            logger.info("Initializing databases...")
            
            # Create database connections
            self.create_auth_database()
            self.create_metadata_database()
            
            # Initialize SQLAlchemy engines and session makers
            await self._initialize_sqlalchemy_engines()
            
            # Apply migrations if needed
            migration_config = self.config.get("migrations", {})
            if migration_config.get("auto_migrate", True):
                await self._apply_all_migrations()
            
            self._initialized = True
            logger.info("All databases initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            self._initialized = False
            raise DatabaseError(f"Database initialization failed: {str(e)}")
    
    async def _initialize_sqlalchemy_engines(self) -> None:
        """Initialize SQLAlchemy engines and session makers for async ORM support"""
        try:
            db_config = self.config["database"]
            
            # Create async engines for both databases
            for db_name, db_key in [("auth_db", "auth_db_path"), ("metadata_db", "metadata_db_path")]:
                db_path = db_config[db_key]
                engine_url = f"sqlite+aiosqlite:///{db_path}"
                
                # Create async engine
                engine = create_async_engine(
                    engine_url,
                    echo=False,
                    pool_pre_ping=True,
                    pool_recycle=300
                )
                
                # Create session maker
                session_maker = async_sessionmaker(
                    engine,
                    class_=AsyncSession,
                    expire_on_commit=False
                )
                
                self._engines[db_name] = engine
                self._session_makers[db_name] = session_maker
                
                logger.info(f"SQLAlchemy engine initialized for {db_name}")
                
        except Exception as e:
            logger.error(f"SQLAlchemy engine initialization failed: {e}")
            raise DatabaseError(f"SQLAlchemy initialization failed: {str(e)}")
    
    async def _apply_all_migrations(self) -> None:
        """Apply migrations to all databases"""
        try:
            for db_name in ["auth_db", "metadata_db"]:
                conn = self.get_connection(db_name)
                
                if self._check_migration_needed(conn, db_name):
                    current_version = self._get_schema_version(conn)
                    logger.info(f"Applying migrations for {db_name} from version {current_version}")
                    
                    self._apply_migrations(conn, db_name, from_version=current_version)
                    self._migration_applied[db_name] = True
                    
                    logger.info(f"Migrations applied for {db_name}")
                else:
                    logger.info(f"No migrations needed for {db_name}")
            
        except Exception as e:
            logger.error(f"Failed to apply migrations: {e}")
            raise MigrationError(f"Failed to apply migrations: {str(e)}")
    
    def _check_migration_needed(self, conn: sqlite3.Connection, db_name: str) -> bool:
        """Check if migration is needed"""
        try:
            current_version = self._get_schema_version(conn)
            return current_version < self.CURRENT_SCHEMA_VERSION
        except Exception as e:
            logger.error(f"Failed to check migration status for {db_name}: {e}")
            return True  # Assume migration needed if we can't check
    
    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """Get current schema version"""
        try:
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.Error:
            # Table doesn't exist, assume version 0
            return 0
    
    def _apply_migrations(self, conn: sqlite3.Connection, db_name: str, from_version: int) -> None:
        """Apply migrations to database"""
        try:
            migrations = self._get_migration_scripts(db_name)
            
            # Filter migrations to apply
            migrations_to_apply = [m for m in migrations if m["version"] > from_version]
            migrations_to_apply.sort(key=lambda x: x["version"])
            
            for migration in migrations_to_apply:
                logger.info(f"Applying migration {migration['version']} to {db_name}")
                
                try:
                    conn.execute(migration["script"])
                    
                    # Update version
                    conn.execute(
                        "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                        (migration["version"],)
                    )
                    
                    conn.commit()
                    
                except Exception as e:
                    conn.rollback()
                    raise MigrationError(f"Failed to apply migration {migration['version']}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Migration failed for {db_name}: {e}")
            raise MigrationError(f"Failed to apply migration: {str(e)}")
    
    def _get_migration_scripts(self, db_name: str) -> List[Dict[str, Any]]:
        """Get migration scripts for database"""
        if db_name == "auth_db":
            return [
                {
                    "version": 2,
                    "script": "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;"
                },
                {
                    "version": 3,
                    "script": "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);"
                }
            ]
        elif db_name == "metadata_db":
            return [
                {
                    "version": 2,
                    "script": "CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id);"
                },
                {
                    "version": 3,
                    "script": "CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);"
                }
            ]
        
        return []
    
    def _rollback_migration(self, conn: sqlite3.Connection, db_name: str, to_version: int) -> None:
        """Rollback migrations to specific version"""
        try:
            rollback_scripts = self._get_rollback_scripts(db_name)
            current_version = self._get_schema_version(conn)
            
            # Filter rollback scripts
            scripts_to_apply = [s for s in rollback_scripts if s["version"] > to_version and s["version"] <= current_version]
            scripts_to_apply.sort(key=lambda x: x["version"], reverse=True)
            
            for script in scripts_to_apply:
                conn.execute(script["script"])
            
            # Update version
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (to_version,)
            )
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise MigrationError(f"Failed to rollback migration: {str(e)}")
    
    def _get_rollback_scripts(self, db_name: str) -> List[Dict[str, Any]]:
        """Get rollback scripts for database"""
        # Implementation would include rollback scripts
        return []
    
    def check_database_health(self) -> Dict[str, bool]:
        """Check health of all database connections"""
        health = {}
        
        for name, conn in self._connections.items():
            try:
                # Simple query to test connection
                cursor = conn.execute("SELECT 1")
                result = cursor.fetchone()
                health[name] = result is not None
                
            except Exception as e:
                logger.error(f"Health check failed for database {name}: {e}")
                health[name] = False
        
        health["overall"] = all(health.values())
        return health
    
    def get_database_statistics(self) -> Dict[str, Dict[str, int]]:
        """Get database statistics"""
        stats = {}
        
        for name, conn in self._connections.items():
            try:
                db_stats = {}
                
                # Get table row counts
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    count_cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = count_cursor.fetchone()[0]
                    db_stats[table_name] = count
                
                stats[name] = db_stats
                
            except Exception as e:
                logger.error(f"Failed to get stats for database {name}: {e}")
                stats[name] = {}
        
        return stats
    
    async def cleanup_all_databases(self) -> None:
        """Cleanup all database connections"""
        if not self._initialized:
            logger.warning("Databases not initialized, nothing to cleanup")
            return
        
        logger.info("Cleaning up databases...")
        
        for name, conn in self._connections.items():
            try:
                conn.close()
                logger.debug(f"Closed database connection: {name}")
            except Exception as e:
                logger.error(f"Error closing database connection {name}: {e}")
        
        self._connections.clear()
        self._initialized = False
        logger.info("Database cleanup completed")
    
    @contextmanager
    def _execute_in_transaction(self, conn: sqlite3.Connection, operation: Callable):
        """Execute operation in transaction with rollback on error"""
        try:
            result = operation()
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            raise e
    
    def _backup_database(self, conn: sqlite3.Connection, backup_path: str) -> None:
        """Create database backup"""
        try:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
            
            logger.info(f"Database backup created: {backup_path}")
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise DatabaseError(f"Database backup failed: {str(e)}")
    
    def _restore_database(self, backup_path: str, target_path: str) -> None:
        """Restore database from backup"""
        try:
            backup_conn = sqlite3.connect(backup_path)
            target_conn = sqlite3.connect(target_path)
            
            backup_conn.backup(target_conn)
            
            backup_conn.close()
            target_conn.close()
            
            logger.info(f"Database restored from backup: {backup_path} -> {target_path}")
            
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            raise DatabaseError(f"Database restore failed: {str(e)}")
    
    def _vacuum_database(self, conn: sqlite3.Connection) -> None:
        """Vacuum database to reclaim space"""
        try:
            conn.execute("VACUUM")
            logger.debug("Database vacuum completed")
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")
    
    def _analyze_database(self, conn: sqlite3.Connection) -> None:
        """Analyze database to update statistics"""
        try:
            conn.execute("ANALYZE")
            logger.debug("Database analyze completed")
        except Exception as e:
            logger.error(f"Database analyze failed: {e}")
    
    async def perform_maintenance(self) -> None:
        """Perform database maintenance tasks"""
        logger.info("Starting database maintenance...")
        
        for name, conn in self._connections.items():
            try:
                logger.debug(f"Performing maintenance on {name}")
                self._vacuum_database(conn)
                self._analyze_database(conn)
            except Exception as e:
                logger.error(f"Maintenance failed for {name}: {e}")
        
        logger.info("Database maintenance completed")


# Global database manager instance
database_manager: Optional[DatabaseManager] = None


def initialize_database_manager(config: Dict[str, Any]) -> DatabaseManager:
    """Initialize global database manager instance"""
    global database_manager
    database_manager = DatabaseManager(config=config)
    return database_manager


def get_database_manager() -> Optional[DatabaseManager]:
    """Get global database manager instance"""
    return database_manager