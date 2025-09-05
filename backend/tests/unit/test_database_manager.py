import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sqlite3
import tempfile
import os
from typing import Optional, Dict, Any, List

from app.core.database_manager import DatabaseManager, DatabaseError, MigrationError


class TestDatabaseManager:
    """Test suite for database initialization and migration management"""
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create temporary directory for databases"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_config(self, temp_db_dir):
        """Mock database configuration"""
        return {
            "database": {
                "auth_db_path": os.path.join(temp_db_dir, "auth.db"),
                "metadata_db_path": os.path.join(temp_db_dir, "metadata.db"),
                "connection_timeout": 30,
                "max_connections": 10,
                "enable_wal": True,
                "backup_enabled": True,
                "backup_interval": 3600
            },
            "migrations": {
                "auto_migrate": True,
                "migration_dir": "migrations",
                "create_tables": True
            }
        }
    
    @pytest.fixture
    def db_manager(self, mock_config):
        """Create DatabaseManager instance for testing"""
        return DatabaseManager(config=mock_config)

    # DatabaseManager Initialization Tests
    def test_database_manager_init(self, mock_config):
        """Test DatabaseManager initialization"""
        manager = DatabaseManager(config=mock_config)
        
        assert manager.config == mock_config
        assert manager._connections == {}
        assert manager._initialized == False
        assert manager._migration_applied == {}

    def test_database_manager_init_no_config(self):
        """Test DatabaseManager initialization without config"""
        with pytest.raises(DatabaseError, match="Configuration is required"):
            DatabaseManager(config=None)

    def test_database_manager_init_invalid_config(self):
        """Test DatabaseManager initialization with invalid config"""
        invalid_configs = [
            {},  # Empty config
            {"database": {}},  # Missing required database sections
            {"database": {"auth_db_path": ""}},  # Empty database path
        ]
        
        for invalid_config in invalid_configs:
            with pytest.raises(DatabaseError, match="Invalid database configuration"):
                DatabaseManager(config=invalid_config)

    # Database Connection Tests
    def test_create_auth_database_success(self, db_manager, temp_db_dir):
        """Test successful auth database creation"""
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            conn = db_manager.create_auth_database()
            
            assert conn == mock_conn
            assert "auth_db" in db_manager._connections
            mock_connect.assert_called_once_with(
                os.path.join(temp_db_dir, "auth.db"),
                timeout=30,
                check_same_thread=False
            )

    def test_create_metadata_database_success(self, db_manager, temp_db_dir):
        """Test successful metadata database creation"""
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            conn = db_manager.create_metadata_database()
            
            assert conn == mock_conn
            assert "metadata_db" in db_manager._connections
            mock_connect.assert_called_once_with(
                os.path.join(temp_db_dir, "metadata.db"),
                timeout=30,
                check_same_thread=False
            )

    def test_create_database_connection_failure(self, db_manager):
        """Test database connection failure"""
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Connection failed")
            
            with pytest.raises(DatabaseError, match="Failed to create auth database"):
                db_manager.create_auth_database()

    def test_get_database_connection_success(self, db_manager):
        """Test successful database connection retrieval"""
        mock_conn = Mock()
        db_manager._connections["auth_db"] = mock_conn
        
        conn = db_manager.get_connection("auth_db")
        assert conn == mock_conn

    def test_get_database_connection_not_found(self, db_manager):
        """Test database connection retrieval when not found"""
        with pytest.raises(DatabaseError, match="Database connection 'nonexistent' not found"):
            db_manager.get_connection("nonexistent")

    def test_get_database_connection_optional_success(self, db_manager):
        """Test optional database connection retrieval - exists"""
        mock_conn = Mock()
        db_manager._connections["auth_db"] = mock_conn
        
        conn = db_manager.get_connection_optional("auth_db")
        assert conn == mock_conn

    def test_get_database_connection_optional_not_found(self, db_manager):
        """Test optional database connection retrieval - doesn't exist"""
        conn = db_manager.get_connection_optional("nonexistent")
        assert conn is None

    # Database Configuration Tests
    def test_configure_database_connection(self, db_manager):
        """Test database connection configuration"""
        mock_conn = Mock()
        
        db_manager._configure_connection(mock_conn)
        
        # Verify SQLite pragmas were executed
        expected_calls = [
            ('PRAGMA journal_mode = WAL',),
            ('PRAGMA synchronous = NORMAL',),
            ('PRAGMA cache_size = -64000',),
            ('PRAGMA foreign_keys = ON',),
            ('PRAGMA temp_store = MEMORY',)
        ]
        
        # Check that execute was called with pragma statements
        assert mock_conn.execute.call_count >= 5

    def test_configure_database_without_wal(self, temp_db_dir):
        """Test database configuration without WAL mode"""
        config = {
            "database": {
                "auth_db_path": os.path.join(temp_db_dir, "auth.db"),
                "metadata_db_path": os.path.join(temp_db_dir, "metadata.db"),
                "enable_wal": False
            }
        }
        
        manager = DatabaseManager(config=config)
        mock_conn = Mock()
        
        manager._configure_connection(mock_conn)
        
        # Should not set WAL mode
        calls = [call[0][0] for call in mock_conn.execute.call_args_list]
        wal_calls = [call for call in calls if "journal_mode = WAL" in call]
        assert len(wal_calls) == 0

    # Table Creation Tests
    def test_create_auth_tables_success(self, db_manager):
        """Test successful auth tables creation"""
        mock_conn = Mock()
        
        db_manager._create_auth_tables(mock_conn)
        
        # Verify table creation SQL was executed
        assert mock_conn.execute.called
        assert mock_conn.commit.called

    def test_create_metadata_tables_success(self, db_manager):
        """Test successful metadata tables creation"""
        mock_conn = Mock()
        
        db_manager._create_metadata_tables(mock_conn)
        
        # Verify table creation SQL was executed
        assert mock_conn.execute.called
        assert mock_conn.commit.called

    def test_create_tables_sql_error(self, db_manager):
        """Test table creation with SQL error"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = sqlite3.Error("Table creation failed")
        
        with pytest.raises(DatabaseError, match="Failed to create auth tables"):
            db_manager._create_auth_tables(mock_conn)

    def test_get_auth_table_schemas(self, db_manager):
        """Test auth table schema retrieval"""
        schemas = db_manager._get_auth_table_schemas()
        
        assert isinstance(schemas, dict)
        assert "users" in schemas
        assert "sessions" in schemas
        
        # Verify SQL structure
        for table_name, schema in schemas.items():
            assert "CREATE TABLE" in schema
            assert table_name in schema

    def test_get_metadata_table_schemas(self, db_manager):
        """Test metadata table schema retrieval"""
        schemas = db_manager._get_metadata_table_schemas()
        
        assert isinstance(schemas, dict)
        assert "documents" in schemas
        assert "document_chunks" in schemas
        assert "workspaces" in schemas
        
        # Verify SQL structure
        for table_name, schema in schemas.items():
            assert "CREATE TABLE" in schema
            assert table_name in schema

    # Migration Tests
    def test_check_migration_needed_new_database(self, db_manager):
        """Test migration check for new database"""
        mock_conn = Mock()
        
        # Mock empty result for version query
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        
        needs_migration = db_manager._check_migration_needed(mock_conn, "auth_db")
        
        assert needs_migration == True

    def test_check_migration_needed_current_version(self, db_manager):
        """Test migration check for current version database"""
        mock_conn = Mock()
        
        # Mock current version result
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (db_manager.CURRENT_SCHEMA_VERSION,)
        mock_conn.execute.return_value = mock_cursor
        
        needs_migration = db_manager._check_migration_needed(mock_conn, "auth_db")
        
        assert needs_migration == False

    def test_check_migration_needed_old_version(self, db_manager):
        """Test migration check for old version database"""
        mock_conn = Mock()
        
        # Mock old version result
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)  # Older than current
        mock_conn.execute.return_value = mock_cursor
        
        needs_migration = db_manager._check_migration_needed(mock_conn, "auth_db")
        
        assert needs_migration == True

    def test_apply_migrations_success(self, db_manager):
        """Test successful migration application"""
        mock_conn = Mock()
        
        with patch.object(db_manager, '_get_migration_scripts') as mock_scripts:
            mock_scripts.return_value = [
                {"version": 2, "script": "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;"},
                {"version": 3, "script": "CREATE INDEX idx_users_email ON users(email);"}
            ]
            
            db_manager._apply_migrations(mock_conn, "auth_db", from_version=1)
            
            # Verify migrations were applied
            assert mock_conn.execute.call_count >= 2
            assert mock_conn.commit.called

    def test_apply_migrations_failure(self, db_manager):
        """Test migration application failure"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = sqlite3.Error("Migration failed")
        
        with patch.object(db_manager, '_get_migration_scripts') as mock_scripts:
            mock_scripts.return_value = [
                {"version": 2, "script": "INVALID SQL;"}
            ]
            
            with pytest.raises(MigrationError, match="Failed to apply migration"):
                db_manager._apply_migrations(mock_conn, "auth_db", from_version=1)

    def test_get_migration_scripts_auth(self, db_manager):
        """Test auth database migration scripts"""
        scripts = db_manager._get_migration_scripts("auth_db")
        
        assert isinstance(scripts, list)
        
        # Verify script structure
        for script in scripts:
            assert "version" in script
            assert "script" in script
            assert isinstance(script["version"], int)
            assert isinstance(script["script"], str)

    def test_get_migration_scripts_metadata(self, db_manager):
        """Test metadata database migration scripts"""
        scripts = db_manager._get_migration_scripts("metadata_db")
        
        assert isinstance(scripts, list)
        
        # Verify script structure
        for script in scripts:
            assert "version" in script
            assert "script" in script

    def test_rollback_migration(self, db_manager):
        """Test migration rollback"""
        mock_conn = Mock()
        
        with patch.object(db_manager, '_get_rollback_scripts') as mock_rollback:
            mock_rollback.return_value = [
                {"version": 3, "script": "DROP INDEX idx_users_email;"},
                {"version": 2, "script": "ALTER TABLE users DROP COLUMN email_verified;"}
            ]
            
            db_manager._rollback_migration(mock_conn, "auth_db", to_version=1)
            
            # Verify rollback was applied
            assert mock_conn.execute.called
            assert mock_conn.commit.called

    # Full Database Initialization Tests
    @pytest.mark.asyncio
    async def test_initialize_all_databases_success(self, db_manager):
        """Test complete database initialization"""
        with patch.object(db_manager, 'create_auth_database') as mock_auth, \
             patch.object(db_manager, 'create_metadata_database') as mock_metadata, \
             patch.object(db_manager, '_check_migration_needed') as mock_check, \
             patch.object(db_manager, '_apply_migrations') as mock_migrate:
            
            mock_auth_conn = Mock()
            mock_metadata_conn = Mock()
            mock_auth.return_value = mock_auth_conn
            mock_metadata.return_value = mock_metadata_conn
            mock_check.return_value = False  # No migration needed
            
            await db_manager.initialize_all_databases()
            
            assert db_manager._initialized == True
            mock_auth.assert_called_once()
            mock_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_all_databases_with_migration(self, db_manager):
        """Test database initialization with migration"""
        with patch.object(db_manager, 'create_auth_database') as mock_auth, \
             patch.object(db_manager, 'create_metadata_database') as mock_metadata, \
             patch.object(db_manager, '_check_migration_needed') as mock_check, \
             patch.object(db_manager, '_apply_migrations') as mock_migrate:
            
            mock_auth_conn = Mock()
            mock_metadata_conn = Mock()
            mock_auth.return_value = mock_auth_conn
            mock_metadata.return_value = mock_metadata_conn
            mock_check.return_value = True  # Migration needed
            
            await db_manager.initialize_all_databases()
            
            assert db_manager._initialized == True
            mock_migrate.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_all_databases_already_initialized(self, db_manager):
        """Test initialization when already initialized"""
        db_manager._initialized = True
        
        with patch.object(db_manager, 'create_auth_database') as mock_auth:
            await db_manager.initialize_all_databases()
            
            # Should not create databases again
            mock_auth.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_all_databases_failure(self, db_manager):
        """Test initialization failure handling"""
        with patch.object(db_manager, 'create_auth_database') as mock_auth:
            mock_auth.side_effect = DatabaseError("Connection failed")
            
            with pytest.raises(DatabaseError, match="Database initialization failed"):
                await db_manager.initialize_all_databases()
            
            assert db_manager._initialized == False

    # Database Health and Status Tests
    def test_check_database_health_success(self, db_manager):
        """Test database health check success"""
        mock_auth_conn = Mock()
        mock_metadata_conn = Mock()
        
        # Mock successful queries
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)
        mock_auth_conn.execute.return_value = mock_cursor
        mock_metadata_conn.execute.return_value = mock_cursor
        
        db_manager._connections = {
            "auth_db": mock_auth_conn,
            "metadata_db": mock_metadata_conn
        }
        
        health = db_manager.check_database_health()
        
        assert health["auth_db"] == True
        assert health["metadata_db"] == True
        assert health["overall"] == True

    def test_check_database_health_failure(self, db_manager):
        """Test database health check failure"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = sqlite3.Error("Query failed")
        
        db_manager._connections = {"auth_db": mock_conn}
        
        health = db_manager.check_database_health()
        
        assert health["auth_db"] == False
        assert health["overall"] == False

    def test_get_database_statistics(self, db_manager):
        """Test database statistics retrieval"""
        mock_auth_conn = Mock()
        mock_metadata_conn = Mock()
        
        # Mock statistics queries
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ("users", 150),
            ("sessions", 25)
        ]
        mock_auth_conn.execute.return_value = mock_cursor
        mock_metadata_conn.execute.return_value = mock_cursor
        
        db_manager._connections = {
            "auth_db": mock_auth_conn,
            "metadata_db": mock_metadata_conn
        }
        
        stats = db_manager.get_database_statistics()
        
        assert "auth_db" in stats
        assert "metadata_db" in stats

    def test_get_schema_version(self, db_manager):
        """Test schema version retrieval"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (3,)
        mock_conn.execute.return_value = mock_cursor
        
        version = db_manager._get_schema_version(mock_conn)
        
        assert version == 3

    def test_get_schema_version_no_version_table(self, db_manager):
        """Test schema version retrieval when version table doesn't exist"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = sqlite3.Error("no such table: schema_version")
        
        version = db_manager._get_schema_version(mock_conn)
        
        assert version == 0

    # Database Cleanup Tests
    @pytest.mark.asyncio
    async def test_cleanup_databases_success(self, db_manager):
        """Test successful database cleanup"""
        mock_auth_conn = Mock()
        mock_metadata_conn = Mock()
        
        db_manager._connections = {
            "auth_db": mock_auth_conn,
            "metadata_db": mock_metadata_conn
        }
        db_manager._initialized = True
        
        await db_manager.cleanup_all_databases()
        
        assert db_manager._initialized == False
        assert len(db_manager._connections) == 0
        mock_auth_conn.close.assert_called_once()
        mock_metadata_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_databases_with_errors(self, db_manager):
        """Test database cleanup with connection errors"""
        mock_conn = Mock()
        mock_conn.close.side_effect = sqlite3.Error("Close failed")
        
        db_manager._connections = {"auth_db": mock_conn}
        db_manager._initialized = True
        
        # Should not raise exception
        await db_manager.cleanup_all_databases()
        
        assert db_manager._initialized == False
        assert len(db_manager._connections) == 0

    # Backup and Recovery Tests
    def test_backup_database_success(self, db_manager, temp_db_dir):
        """Test successful database backup"""
        mock_conn = Mock()
        backup_path = os.path.join(temp_db_dir, "backup.db")
        
        with patch('sqlite3.connect') as mock_backup_connect:
            mock_backup_conn = Mock()
            mock_backup_connect.return_value = mock_backup_conn
            
            db_manager._backup_database(mock_conn, backup_path)
            
            mock_conn.backup.assert_called_once_with(mock_backup_conn)
            mock_backup_conn.close.assert_called_once()

    def test_backup_database_failure(self, db_manager, temp_db_dir):
        """Test database backup failure"""
        mock_conn = Mock()
        mock_conn.backup.side_effect = sqlite3.Error("Backup failed")
        backup_path = os.path.join(temp_db_dir, "backup.db")
        
        with patch('sqlite3.connect'):
            with pytest.raises(DatabaseError, match="Database backup failed"):
                db_manager._backup_database(mock_conn, backup_path)

    def test_restore_database_success(self, db_manager, temp_db_dir):
        """Test successful database restore"""
        backup_path = os.path.join(temp_db_dir, "backup.db")
        target_path = os.path.join(temp_db_dir, "restored.db")
        
        with patch('sqlite3.connect') as mock_connect:
            mock_backup_conn = Mock()
            mock_target_conn = Mock()
            mock_connect.side_effect = [mock_backup_conn, mock_target_conn]
            
            db_manager._restore_database(backup_path, target_path)
            
            mock_backup_conn.backup.assert_called_once_with(mock_target_conn)

    # Connection Pool Tests
    def test_connection_pool_management(self, db_manager):
        """Test connection pool management"""
        # Test connection limits
        max_connections = db_manager.config["database"]["max_connections"]
        
        connections = []
        for i in range(max_connections + 5):  # Try to exceed limit
            try:
                conn = Mock()
                db_manager._connections[f"conn_{i}"] = conn
                connections.append(conn)
            except DatabaseError:
                break
        
        # Should respect connection limits
        assert len(db_manager._connections) <= max_connections

    # Transaction Management Tests
    def test_execute_in_transaction_success(self, db_manager):
        """Test successful transaction execution"""
        mock_conn = Mock()
        
        def test_operation():
            mock_conn.execute("INSERT INTO test VALUES (1)")
            return "success"
        
        result = db_manager._execute_in_transaction(mock_conn, test_operation)
        
        assert result == "success"
        mock_conn.commit.assert_called_once()

    def test_execute_in_transaction_failure(self, db_manager):
        """Test transaction execution with rollback"""
        mock_conn = Mock()
        
        def failing_operation():
            mock_conn.execute("INSERT INTO test VALUES (1)")
            raise sqlite3.Error("Operation failed")
        
        with pytest.raises(sqlite3.Error):
            db_manager._execute_in_transaction(mock_conn, failing_operation)
        
        mock_conn.rollback.assert_called_once()

    # Database Maintenance Tests
    def test_vacuum_database(self, db_manager):
        """Test database vacuum operation"""
        mock_conn = Mock()
        
        db_manager._vacuum_database(mock_conn)
        
        mock_conn.execute.assert_called_with("VACUUM")

    def test_analyze_database(self, db_manager):
        """Test database analyze operation"""
        mock_conn = Mock()
        
        db_manager._analyze_database(mock_conn)
        
        mock_conn.execute.assert_called_with("ANALYZE")

    @pytest.mark.asyncio
    async def test_maintenance_task(self, db_manager):
        """Test scheduled database maintenance"""
        mock_conn = Mock()
        db_manager._connections = {"auth_db": mock_conn}
        
        with patch.object(db_manager, '_vacuum_database') as mock_vacuum, \
             patch.object(db_manager, '_analyze_database') as mock_analyze:
            
            await db_manager.perform_maintenance()
            
            mock_vacuum.assert_called()
            mock_analyze.assert_called()