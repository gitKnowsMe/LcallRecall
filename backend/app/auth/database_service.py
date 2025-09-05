"""
Database service for authentication - bridges old and new database systems
"""
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from ..core.database_manager import get_database_manager

logger = logging.getLogger(__name__)


class DatabaseService:
    """Database service for authentication operations"""
    
    def __init__(self):
        self.database_manager = None
        self._initialized = False
    
    def initialize(self):
        """Initialize database service with database manager"""
        self.database_manager = get_database_manager()
        if self.database_manager:
            self._initialized = True
            logger.info("DatabaseService initialized with DatabaseManager")
        else:
            logger.warning("DatabaseService initialized without DatabaseManager - using fallback")
    
    @contextmanager
    def get_auth_db_connection(self):
        """Get auth database connection"""
        if not self._initialized:
            self.initialize()
        
        if self.database_manager and self._initialized:
            try:
                conn = self.database_manager.get_connection("auth_db")
                yield conn
            except Exception as e:
                logger.error(f"Failed to get auth database connection: {e}")
                raise RuntimeError("Auth database not initialized")
        else:
            raise RuntimeError("Auth database not initialized")
    
    def execute_query(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a single query and return one result"""
        try:
            with self.get_auth_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_query_many(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a query and return all results"""
        try:
            with self.get_auth_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Execute insert query and return last row id"""
        try:
            with self.get_auth_db_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Insert execution failed: {e}")
            raise
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute update query and return affected rows"""
        try:
            with self.get_auth_db_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Update execution failed: {e}")
            raise
    
    def get_next_workspace_id(self) -> int:
        """Get next available workspace ID"""
        try:
            result = self.execute_query(
                "SELECT MAX(CAST(workspace_id AS INTEGER)) as max_workspace FROM users WHERE workspace_id GLOB '[0-9]*'"
            )
            if result and result['max_workspace'] is not None:
                return result['max_workspace'] + 1
            return 1
        except Exception as e:
            logger.error(f"Failed to get next workspace ID: {e}")
            return 1


# Global database service instance
database_service = DatabaseService()