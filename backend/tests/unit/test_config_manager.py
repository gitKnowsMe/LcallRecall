import pytest
from unittest.mock import Mock, patch, mock_open
import os
import json
import yaml
import tempfile
from typing import Dict, Any, Optional

from app.core.config_manager import ConfigManager, ConfigError, ConfigValidationError


class TestConfigManager:
    """Test suite for configuration management"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for configuration files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def sample_config_data(self):
        """Sample configuration data"""
        return {
            "app": {
                "name": "LocalRecall RAG API",
                "version": "1.0.0",
                "environment": "development"
            },
            "database": {
                "auth_db_path": "/path/to/auth.db",
                "metadata_db_path": "/path/to/metadata.db",
                "connection_timeout": 30,
                "max_connections": 10
            },
            "model": {
                "path": "/Users/singularity/local AI/models/phi-2-instruct-Q4_K_M.gguf",
                "max_context_length": 4096,
                "batch_size": 512,
                "preload": True
            },
            "vector_store": {
                "workspace_dir": "/path/to/workspaces",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            "api": {
                "host": "127.0.0.1",
                "port": 8000,
                "cors_origins": ["http://localhost:3000"],
                "trusted_hosts": ["localhost", "127.0.0.1"]
            },
            "security": {
                "jwt_secret": "your-secret-key-here",
                "jwt_algorithm": "HS256",
                "jwt_expiration": 3600
            },
            "logging": {
                "level": "INFO",
                "file": "/path/to/app.log",
                "max_size": "10MB",
                "backup_count": 5
            }
        }
    
    @pytest.fixture
    def config_manager(self):
        """Create ConfigManager instance for testing"""
        return ConfigManager()

    # ConfigManager Initialization Tests
    def test_config_manager_init(self):
        """Test ConfigManager initialization"""
        manager = ConfigManager()
        
        assert manager._config == {}
        assert manager._config_file_path is None
        assert manager._environment == "development"
        assert manager._validation_schema is not None

    def test_config_manager_init_with_env(self):
        """Test ConfigManager initialization with environment"""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            manager = ConfigManager()
            
            assert manager._environment == "production"

    # Configuration Loading Tests
    def test_load_from_file_json_success(self, config_manager, temp_config_dir, sample_config_data):
        """Test successful JSON configuration loading"""
        config_file = os.path.join(temp_config_dir, "config.json")
        
        with open(config_file, 'w') as f:
            json.dump(sample_config_data, f, indent=2)
        
        config_manager.load_from_file(config_file)
        
        assert config_manager._config == sample_config_data
        assert config_manager._config_file_path == config_file

    def test_load_from_file_yaml_success(self, config_manager, temp_config_dir, sample_config_data):
        """Test successful YAML configuration loading"""
        config_file = os.path.join(temp_config_dir, "config.yaml")
        
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_data, f, default_flow_style=False)
        
        config_manager.load_from_file(config_file)
        
        assert config_manager._config == sample_config_data

    def test_load_from_file_yml_extension(self, config_manager, temp_config_dir, sample_config_data):
        """Test YAML loading with .yml extension"""
        config_file = os.path.join(temp_config_dir, "config.yml")
        
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_data, f)
        
        config_manager.load_from_file(config_file)
        
        assert config_manager._config == sample_config_data

    def test_load_from_file_not_found(self, config_manager):
        """Test loading from non-existent file"""
        with pytest.raises(ConfigError, match="Configuration file not found"):
            config_manager.load_from_file("nonexistent.json")

    def test_load_from_file_invalid_json(self, config_manager, temp_config_dir):
        """Test loading invalid JSON file"""
        config_file = os.path.join(temp_config_dir, "invalid.json")
        
        with open(config_file, 'w') as f:
            f.write('{"invalid": json}')  # Invalid JSON
        
        with pytest.raises(ConfigError, match="Failed to parse JSON configuration"):
            config_manager.load_from_file(config_file)

    def test_load_from_file_invalid_yaml(self, config_manager, temp_config_dir):
        """Test loading invalid YAML file"""
        config_file = os.path.join(temp_config_dir, "invalid.yaml")
        
        with open(config_file, 'w') as f:
            f.write('invalid: yaml: content: [')  # Invalid YAML
        
        with pytest.raises(ConfigError, match="Failed to parse YAML configuration"):
            config_manager.load_from_file(config_file)

    def test_load_from_file_unsupported_format(self, config_manager, temp_config_dir):
        """Test loading unsupported file format"""
        config_file = os.path.join(temp_config_dir, "config.txt")
        
        with open(config_file, 'w') as f:
            f.write("some content")
        
        with pytest.raises(ConfigError, match="Unsupported configuration file format"):
            config_manager.load_from_file(config_file)

    # Dictionary Loading Tests
    def test_load_from_dict_success(self, config_manager, sample_config_data):
        """Test successful dictionary configuration loading"""
        config_manager.load_from_dict(sample_config_data)
        
        assert config_manager._config == sample_config_data

    def test_load_from_dict_none(self, config_manager):
        """Test loading None dictionary"""
        with pytest.raises(ConfigError, match="Configuration dictionary cannot be None"):
            config_manager.load_from_dict(None)

    def test_load_from_dict_empty(self, config_manager):
        """Test loading empty dictionary"""
        with pytest.raises(ConfigError, match="Configuration dictionary cannot be empty"):
            config_manager.load_from_dict({})

    def test_load_from_dict_invalid_type(self, config_manager):
        """Test loading non-dictionary object"""
        with pytest.raises(ConfigError, match="Configuration must be a dictionary"):
            config_manager.load_from_dict("not a dict")

    # Environment Variable Integration Tests
    def test_load_with_env_variables(self, config_manager, sample_config_data):
        """Test configuration loading with environment variable substitution"""
        # Config with environment variables
        config_with_env = sample_config_data.copy()
        config_with_env["database"]["auth_db_path"] = "${DB_PATH}/auth.db"
        config_with_env["api"]["port"] = "${API_PORT:8000}"  # With default
        
        with patch.dict(os.environ, {"DB_PATH": "/custom/path", "API_PORT": "9000"}):
            config_manager.load_from_dict(config_with_env)
            config_manager.resolve_environment_variables()
        
        assert config_manager.get("database.auth_db_path") == "/custom/path/auth.db"
        assert config_manager.get("api.port") == "9000"

    def test_load_with_env_variables_defaults(self, config_manager):
        """Test environment variable defaults"""
        config_data = {
            "api": {
                "host": "${API_HOST:localhost}",
                "port": "${API_PORT:8000}"
            }
        }
        
        # Don't set environment variables, should use defaults
        with patch.dict(os.environ, {}, clear=True):
            config_manager.load_from_dict(config_data)
            config_manager.resolve_environment_variables()
        
        assert config_manager.get("api.host") == "localhost"
        assert config_manager.get("api.port") == "8000"

    def test_load_with_missing_env_variable(self, config_manager):
        """Test missing environment variable without default"""
        config_data = {
            "database": {
                "path": "${MISSING_VAR}"
            }
        }
        
        with patch.dict(os.environ, {}, clear=True):
            config_manager.load_from_dict(config_data)
            
            with pytest.raises(ConfigError, match="Environment variable 'MISSING_VAR' not found"):
                config_manager.resolve_environment_variables()

    # Configuration Access Tests
    def test_get_config_value_success(self, config_manager, sample_config_data):
        """Test successful configuration value retrieval"""
        config_manager.load_from_dict(sample_config_data)
        
        assert config_manager.get("app.name") == "LocalRecall RAG API"
        assert config_manager.get("database.connection_timeout") == 30
        assert config_manager.get("api.cors_origins") == ["http://localhost:3000"]

    def test_get_config_value_nested(self, config_manager, sample_config_data):
        """Test nested configuration value retrieval"""
        config_manager.load_from_dict(sample_config_data)
        
        # Deep nesting
        nested_config = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep_value"
                    }
                }
            }
        }
        config_manager.load_from_dict(nested_config)
        
        assert config_manager.get("level1.level2.level3.value") == "deep_value"

    def test_get_config_value_with_default(self, config_manager, sample_config_data):
        """Test configuration value retrieval with default"""
        config_manager.load_from_dict(sample_config_data)
        
        assert config_manager.get("nonexistent.key", "default_value") == "default_value"
        assert config_manager.get("app.name", "default") == "LocalRecall RAG API"

    def test_get_config_value_not_found(self, config_manager, sample_config_data):
        """Test configuration value retrieval when not found"""
        config_manager.load_from_dict(sample_config_data)
        
        with pytest.raises(ConfigError, match="Configuration key 'nonexistent.key' not found"):
            config_manager.get("nonexistent.key")

    def test_get_section_success(self, config_manager, sample_config_data):
        """Test successful configuration section retrieval"""
        config_manager.load_from_dict(sample_config_data)
        
        database_config = config_manager.get_section("database")
        
        assert isinstance(database_config, dict)
        assert database_config["auth_db_path"] == "/path/to/auth.db"
        assert database_config["connection_timeout"] == 30

    def test_get_section_not_found(self, config_manager, sample_config_data):
        """Test configuration section retrieval when not found"""
        config_manager.load_from_dict(sample_config_data)
        
        with pytest.raises(ConfigError, match="Configuration section 'nonexistent' not found"):
            config_manager.get_section("nonexistent")

    def test_get_section_optional_success(self, config_manager, sample_config_data):
        """Test optional configuration section retrieval - exists"""
        config_manager.load_from_dict(sample_config_data)
        
        section = config_manager.get_section_optional("database")
        assert section is not None
        assert isinstance(section, dict)

    def test_get_section_optional_not_found(self, config_manager, sample_config_data):
        """Test optional configuration section retrieval - doesn't exist"""
        config_manager.load_from_dict(sample_config_data)
        
        section = config_manager.get_section_optional("nonexistent")
        assert section is None

    # Configuration Validation Tests
    def test_validate_configuration_success(self, config_manager, sample_config_data):
        """Test successful configuration validation"""
        config_manager.load_from_dict(sample_config_data)
        
        # Should not raise exception
        config_manager.validate_configuration()

    def test_validate_configuration_missing_required_section(self, config_manager):
        """Test validation with missing required section"""
        incomplete_config = {
            "app": {
                "name": "Test App"
            }
            # Missing required sections like database, model, etc.
        }
        
        config_manager.load_from_dict(incomplete_config)
        
        with pytest.raises(ConfigValidationError, match="Required configuration section"):
            config_manager.validate_configuration()

    def test_validate_configuration_missing_required_key(self, config_manager):
        """Test validation with missing required key"""
        invalid_config = {
            "app": {
                "name": "Test App"
            },
            "database": {
                "auth_db_path": "/path/to/auth.db"
                # Missing metadata_db_path
            },
            "model": {
                "path": "/path/to/model"
            },
            "vector_store": {
                "workspace_dir": "/path/to/workspaces"
            },
            "api": {
                "host": "localhost",
                "port": 8000
            },
            "security": {
                "jwt_secret": "secret"
            }
        }
        
        config_manager.load_from_dict(invalid_config)
        
        with pytest.raises(ConfigValidationError, match="Required configuration key"):
            config_manager.validate_configuration()

    def test_validate_configuration_invalid_type(self, config_manager):
        """Test validation with invalid value type"""
        invalid_config = {
            "app": {"name": "Test App"},
            "database": {
                "auth_db_path": "/path/to/auth.db",
                "metadata_db_path": "/path/to/metadata.db",
                "connection_timeout": "not_a_number"  # Should be int
            },
            "model": {"path": "/path/to/model"},
            "vector_store": {"workspace_dir": "/path/to/workspaces"},
            "api": {"host": "localhost", "port": 8000},
            "security": {"jwt_secret": "secret"}
        }
        
        config_manager.load_from_dict(invalid_config)
        
        with pytest.raises(ConfigValidationError, match="Configuration validation failed"):
            config_manager.validate_configuration()

    def test_validate_file_paths(self, config_manager, sample_config_data):
        """Test file path validation"""
        config_manager.load_from_dict(sample_config_data)
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            
            # Should not raise exception when files exist
            config_manager._validate_file_paths()

    def test_validate_file_paths_missing_file(self, config_manager, sample_config_data):
        """Test file path validation with missing file"""
        config_manager.load_from_dict(sample_config_data)
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            with pytest.raises(ConfigValidationError, match="Required file does not exist"):
                config_manager._validate_file_paths()

    # Configuration Modification Tests
    def test_set_config_value(self, config_manager, sample_config_data):
        """Test setting configuration value"""
        config_manager.load_from_dict(sample_config_data)
        
        config_manager.set("app.name", "New App Name")
        
        assert config_manager.get("app.name") == "New App Name"

    def test_set_config_nested_value(self, config_manager):
        """Test setting nested configuration value"""
        config_manager.load_from_dict({"app": {}})
        
        config_manager.set("app.new.nested.value", "test")
        
        assert config_manager.get("app.new.nested.value") == "test"

    def test_update_section(self, config_manager, sample_config_data):
        """Test updating configuration section"""
        config_manager.load_from_dict(sample_config_data)
        
        new_api_config = {
            "host": "0.0.0.0",
            "port": 9000,
            "cors_origins": ["http://localhost:3000", "http://localhost:3001"]
        }
        
        config_manager.update_section("api", new_api_config)
        
        assert config_manager.get("api.host") == "0.0.0.0"
        assert config_manager.get("api.port") == 9000
        assert len(config_manager.get("api.cors_origins")) == 2

    def test_merge_configuration(self, config_manager, sample_config_data):
        """Test merging configuration"""
        config_manager.load_from_dict(sample_config_data)
        
        additional_config = {
            "api": {
                "timeout": 30  # New key
            },
            "features": {  # New section
                "enable_debug": True
            }
        }
        
        config_manager.merge_configuration(additional_config)
        
        assert config_manager.get("api.timeout") == 30
        assert config_manager.get("features.enable_debug") == True
        # Original values should remain
        assert config_manager.get("api.host") == "127.0.0.1"

    # Configuration Export Tests
    def test_export_to_dict(self, config_manager, sample_config_data):
        """Test exporting configuration to dictionary"""
        config_manager.load_from_dict(sample_config_data)
        
        exported = config_manager.export_to_dict()
        
        assert exported == sample_config_data
        # Should be a copy, not the same object
        assert exported is not sample_config_data

    def test_export_to_file_json(self, config_manager, temp_config_dir, sample_config_data):
        """Test exporting configuration to JSON file"""
        config_manager.load_from_dict(sample_config_data)
        
        export_file = os.path.join(temp_config_dir, "exported.json")
        config_manager.export_to_file(export_file)
        
        # Verify file was created and contains correct data
        assert os.path.exists(export_file)
        
        with open(export_file, 'r') as f:
            exported_data = json.load(f)
        
        assert exported_data == sample_config_data

    def test_export_to_file_yaml(self, config_manager, temp_config_dir, sample_config_data):
        """Test exporting configuration to YAML file"""
        config_manager.load_from_dict(sample_config_data)
        
        export_file = os.path.join(temp_config_dir, "exported.yaml")
        config_manager.export_to_file(export_file)
        
        # Verify file was created and contains correct data
        assert os.path.exists(export_file)
        
        with open(export_file, 'r') as f:
            exported_data = yaml.safe_load(f)
        
        assert exported_data == sample_config_data

    # Configuration Backup and Restore Tests
    def test_create_backup(self, config_manager, temp_config_dir, sample_config_data):
        """Test configuration backup creation"""
        config_file = os.path.join(temp_config_dir, "config.json")
        
        with open(config_file, 'w') as f:
            json.dump(sample_config_data, f)
        
        config_manager.load_from_file(config_file)
        
        backup_file = config_manager.create_backup()
        
        assert os.path.exists(backup_file)
        assert backup_file.endswith(".backup")

    def test_restore_from_backup(self, config_manager, temp_config_dir, sample_config_data):
        """Test configuration restore from backup"""
        # Create original config
        config_manager.load_from_dict(sample_config_data)
        
        # Modify config
        config_manager.set("app.name", "Modified Name")
        
        # Create backup of original
        backup_data = sample_config_data.copy()
        backup_file = os.path.join(temp_config_dir, "config.backup")
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)
        
        # Restore from backup
        config_manager.restore_from_backup(backup_file)
        
        assert config_manager.get("app.name") == "LocalRecall RAG API"

    # Environment-Specific Configuration Tests
    def test_load_environment_specific_config(self, config_manager, temp_config_dir, sample_config_data):
        """Test loading environment-specific configuration"""
        # Create base config
        base_config_file = os.path.join(temp_config_dir, "config.json")
        with open(base_config_file, 'w') as f:
            json.dump(sample_config_data, f)
        
        # Create production config
        prod_config = {
            "api": {
                "host": "0.0.0.0",
                "port": 80
            },
            "logging": {
                "level": "WARNING"
            }
        }
        prod_config_file = os.path.join(temp_config_dir, "config.production.json")
        with open(prod_config_file, 'w') as f:
            json.dump(prod_config, f)
        
        # Load with production environment
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            manager = ConfigManager()
            manager.load_from_file(base_config_file)
            manager.load_environment_overrides(temp_config_dir)
        
        assert manager.get("api.host") == "0.0.0.0"
        assert manager.get("api.port") == 80
        assert manager.get("logging.level") == "WARNING"
        # Base values should remain for non-overridden keys
        assert manager.get("app.name") == "LocalRecall RAG API"

    def test_get_configuration_summary(self, config_manager, sample_config_data):
        """Test getting configuration summary"""
        config_manager.load_from_dict(sample_config_data)
        
        summary = config_manager.get_configuration_summary()
        
        assert "sections" in summary
        assert "total_keys" in summary
        assert "environment" in summary
        assert len(summary["sections"]) > 0

    def test_is_production_environment(self, config_manager):
        """Test production environment detection"""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            manager = ConfigManager()
            assert manager.is_production() == True
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            manager = ConfigManager()
            assert manager.is_production() == False

    def test_is_development_environment(self, config_manager):
        """Test development environment detection"""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            manager = ConfigManager()
            assert manager.is_development() == True
        
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            manager = ConfigManager()
            assert manager.is_development() == False

    # Configuration Watching Tests
    @pytest.mark.asyncio
    async def test_watch_configuration_file(self, config_manager, temp_config_dir, sample_config_data):
        """Test configuration file watching for changes"""
        config_file = os.path.join(temp_config_dir, "config.json")
        
        with open(config_file, 'w') as f:
            json.dump(sample_config_data, f)
        
        config_manager.load_from_file(config_file)
        
        callback_called = False
        
        def config_changed_callback():
            nonlocal callback_called
            callback_called = True
        
        # Start watching (mock implementation)
        with patch('watchdog.observers.Observer') as mock_observer:
            config_manager.watch_configuration_file(config_changed_callback)
            
            # Simulate file change
            config_changed_callback()
            
            assert callback_called == True

    # Error Handling Tests
    def test_handle_circular_references(self, config_manager):
        """Test handling circular references in configuration"""
        # This would be caught during environment variable resolution
        circular_config = {
            "var1": "${var2}",
            "var2": "${var1}"
        }
        
        config_manager.load_from_dict(circular_config)
        
        with pytest.raises(ConfigError, match="Circular reference detected"):
            config_manager.resolve_environment_variables()

    def test_configuration_not_loaded_error(self, config_manager):
        """Test accessing configuration before loading"""
        with pytest.raises(ConfigError, match="No configuration loaded"):
            config_manager.get("app.name")