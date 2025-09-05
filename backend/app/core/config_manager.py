import os
import json
import yaml
import logging
import re
import time
from typing import Dict, Any, Optional, Union
from pathlib import Path
import shutil
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration manager error"""
    pass


class ConfigValidationError(ConfigError):
    """Configuration validation error"""
    pass


class ConfigManager:
    """Manages application configuration loading, validation, and access"""
    
    def __init__(self, environment: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            environment: Environment name (development, production, test)
        """
        self._config: Dict[str, Any] = {}
        self._config_file_path: Optional[str] = None
        self._environment = environment or os.getenv("ENVIRONMENT", "development")
        self._validation_schema = self._get_validation_schema()
        
        logger.info(f"ConfigManager initialized for environment: {self._environment}")
    
    def _get_validation_schema(self) -> Dict[str, Any]:
        """Get configuration validation schema"""
        return {
            "required_sections": [
                "app", "database", "model", "vector_store", "api", "security"
            ],
            "required_keys": {
                "database": ["auth_db_path", "metadata_db_path"],
                "model": ["path"],
                "vector_store": ["workspace_dir"],
                "api": ["host", "port"],
                "security": ["jwt_secret"]
            },
            "type_validation": {
                "database.connection_timeout": int,
                "database.max_connections": int,
                "model.max_context_length": int,
                "model.batch_size": int,
                "api.port": int,
                "security.jwt_expiration": int
            }
        }
    
    def load_from_file(self, file_path: str) -> None:
        """
        Load configuration from file
        
        Args:
            file_path: Path to configuration file (JSON or YAML)
        """
        if not os.path.exists(file_path):
            raise ConfigError(f"Configuration file not found: {file_path}")
        
        try:
            file_ext = Path(file_path).suffix.lower()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_ext == '.json':
                    self._config = json.load(f)
                elif file_ext in ['.yaml', '.yml']:
                    self._config = yaml.safe_load(f)
                else:
                    raise ConfigError(f"Unsupported configuration file format: {file_ext}")
            
            self._config_file_path = file_path
            logger.info(f"Configuration loaded from: {file_path}")
            
        except json.JSONDecodeError as e:
            raise ConfigError(f"Failed to parse JSON configuration: {str(e)}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse YAML configuration: {str(e)}")
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {str(e)}")
    
    def load_from_dict(self, config_dict: Dict[str, Any]) -> None:
        """
        Load configuration from dictionary
        
        Args:
            config_dict: Configuration dictionary
        """
        if config_dict is None:
            raise ConfigError("Configuration dictionary cannot be None")
        
        if not isinstance(config_dict, dict):
            raise ConfigError("Configuration must be a dictionary")
        
        if not config_dict:
            raise ConfigError("Configuration dictionary cannot be empty")
        
        self._config = deepcopy(config_dict)
        logger.info("Configuration loaded from dictionary")
    
    def resolve_environment_variables(self) -> None:
        """Resolve environment variables in configuration values"""
        try:
            self._config = self._resolve_env_vars_recursive(self._config)
            logger.info("Environment variables resolved in configuration")
        except Exception as e:
            raise ConfigError(f"Failed to resolve environment variables: {str(e)}")
    
    def _resolve_env_vars_recursive(self, obj: Any, depth: int = 0) -> Any:
        """Recursively resolve environment variables in configuration"""
        if depth > 10:  # Prevent infinite recursion
            raise ConfigError("Circular reference detected in environment variables")
        
        if isinstance(obj, dict):
            return {key: self._resolve_env_vars_recursive(value, depth + 1) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_env_vars_recursive(item, depth + 1) for item in obj]
        elif isinstance(obj, str):
            return self._resolve_env_var_string(obj)
        else:
            return obj
    
    def _resolve_env_var_string(self, value: str) -> str:
        """Resolve environment variables in string value"""
        # Pattern: ${VAR_NAME} or ${VAR_NAME:default_value}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2)
            
            env_value = os.getenv(var_name)
            
            if env_value is not None:
                return env_value
            elif default_value is not None:
                return default_value
            else:
                raise ConfigError(f"Environment variable '{var_name}' not found and no default provided")
        
        return re.sub(pattern, replace_var, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., "database.host")
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        if not self._config:
            raise ConfigError("No configuration loaded")
        
        try:
            value = self._config
            for part in key.split('.'):
                value = value[part]
            return value
        except (KeyError, TypeError):
            if default is not None:
                return default
            raise ConfigError(f"Configuration key '{key}' not found")
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., "database.host")
            value: Value to set
        """
        if not self._config:
            self._config = {}
        
        config = self._config
        parts = key.split('.')
        
        # Navigate to parent of target key
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        
        # Set final value
        config[parts[-1]] = value
        logger.debug(f"Configuration updated: {key} = {value}")
    
    def get_section(self, section_name: str) -> Dict[str, Any]:
        """
        Get configuration section
        
        Args:
            section_name: Section name
            
        Returns:
            Configuration section
        """
        if not self._config:
            raise ConfigError("No configuration loaded")
        
        if section_name not in self._config:
            raise ConfigError(f"Configuration section '{section_name}' not found")
        
        return deepcopy(self._config[section_name])
    
    def get_section_optional(self, section_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration section if it exists
        
        Args:
            section_name: Section name
            
        Returns:
            Configuration section or None
        """
        if not self._config or section_name not in self._config:
            return None
        
        return deepcopy(self._config[section_name])
    
    def update_section(self, section_name: str, section_data: Dict[str, Any]) -> None:
        """
        Update configuration section
        
        Args:
            section_name: Section name
            section_data: New section data
        """
        if not self._config:
            self._config = {}
        
        self._config[section_name] = deepcopy(section_data)
        logger.debug(f"Configuration section updated: {section_name}")
    
    def merge_configuration(self, additional_config: Dict[str, Any]) -> None:
        """
        Merge additional configuration
        
        Args:
            additional_config: Additional configuration to merge
        """
        self._config = self._deep_merge(self._config, additional_config)
        logger.info("Configuration merged")
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = deepcopy(base)
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result
    
    def validate_configuration(self) -> None:
        """Validate configuration against schema"""
        if not self._config:
            raise ConfigValidationError("No configuration to validate")
        
        try:
            # Check required sections
            for section in self._validation_schema["required_sections"]:
                if section not in self._config:
                    raise ConfigValidationError(f"Required configuration section '{section}' is missing")
            
            # Check required keys
            for section, keys in self._validation_schema["required_keys"].items():
                if section in self._config:
                    for key in keys:
                        if key not in self._config[section]:
                            raise ConfigValidationError(f"Required configuration key '{section}.{key}' is missing")
            
            # Type validation
            for key_path, expected_type in self._validation_schema["type_validation"].items():
                try:
                    value = self.get(key_path)
                    if not isinstance(value, expected_type):
                        raise ConfigValidationError(f"Configuration key '{key_path}' should be of type {expected_type.__name__}")
                except ConfigError:
                    # Key doesn't exist, skip type check
                    pass
            
            # Validate file paths
            self._validate_file_paths()
            
            logger.info("Configuration validation successful")
            
        except ConfigValidationError:
            raise
        except Exception as e:
            raise ConfigValidationError(f"Configuration validation failed: {str(e)}")
    
    def _validate_file_paths(self) -> None:
        """Validate that required file paths exist"""
        file_path_keys = [
            "model.path"
        ]
        
        for key in file_path_keys:
            try:
                file_path = self.get(key)
                if file_path and not os.path.exists(file_path):
                    raise ConfigValidationError(f"Required file does not exist: {file_path} (key: {key})")
            except ConfigError:
                # Key doesn't exist, skip validation
                pass
    
    def export_to_dict(self) -> Dict[str, Any]:
        """
        Export configuration to dictionary
        
        Returns:
            Configuration dictionary
        """
        return deepcopy(self._config)
    
    def export_to_file(self, file_path: str) -> None:
        """
        Export configuration to file
        
        Args:
            file_path: Output file path
        """
        try:
            file_ext = Path(file_path).suffix.lower()
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                if file_ext == '.json':
                    json.dump(self._config, f, indent=2)
                elif file_ext in ['.yaml', '.yml']:
                    yaml.dump(self._config, f, default_flow_style=False)
                else:
                    raise ConfigError(f"Unsupported export format: {file_ext}")
            
            logger.info(f"Configuration exported to: {file_path}")
            
        except Exception as e:
            raise ConfigError(f"Failed to export configuration: {str(e)}")
    
    def create_backup(self) -> str:
        """
        Create configuration backup
        
        Returns:
            Backup file path
        """
        if not self._config_file_path:
            raise ConfigError("No source configuration file to backup")
        
        timestamp = int(time.time())
        backup_path = f"{self._config_file_path}.{timestamp}.backup"
        
        try:
            shutil.copy2(self._config_file_path, backup_path)
            logger.info(f"Configuration backup created: {backup_path}")
            return backup_path
        except Exception as e:
            raise ConfigError(f"Failed to create backup: {str(e)}")
    
    def restore_from_backup(self, backup_path: str) -> None:
        """
        Restore configuration from backup
        
        Args:
            backup_path: Backup file path
        """
        if not os.path.exists(backup_path):
            raise ConfigError(f"Backup file not found: {backup_path}")
        
        try:
            self.load_from_file(backup_path)
            logger.info(f"Configuration restored from backup: {backup_path}")
        except Exception as e:
            raise ConfigError(f"Failed to restore from backup: {str(e)}")
    
    def load_environment_overrides(self, config_dir: str) -> None:
        """
        Load environment-specific configuration overrides
        
        Args:
            config_dir: Directory containing configuration files
        """
        env_config_file = os.path.join(config_dir, f"config.{self._environment}.json")
        
        if os.path.exists(env_config_file):
            try:
                with open(env_config_file, 'r', encoding='utf-8') as f:
                    env_config = json.load(f)
                
                self.merge_configuration(env_config)
                logger.info(f"Environment overrides loaded: {env_config_file}")
                
            except Exception as e:
                logger.warning(f"Failed to load environment overrides: {e}")
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get configuration summary
        
        Returns:
            Configuration summary
        """
        if not self._config:
            return {"loaded": False}
        
        return {
            "loaded": True,
            "environment": self._environment,
            "sections": list(self._config.keys()),
            "total_keys": self._count_keys_recursive(self._config),
            "source_file": self._config_file_path
        }
    
    def _count_keys_recursive(self, obj: Any) -> int:
        """Count total keys in nested dictionary"""
        if isinstance(obj, dict):
            return len(obj) + sum(self._count_keys_recursive(value) for value in obj.values())
        elif isinstance(obj, list):
            return sum(self._count_keys_recursive(item) for item in obj)
        else:
            return 0
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self._environment.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self._environment.lower() == "development"
    
    def is_test(self) -> bool:
        """Check if running in test environment"""
        return self._environment.lower() == "test"
    
    def watch_configuration_file(self, callback: callable) -> None:
        """
        Watch configuration file for changes
        
        Args:
            callback: Callback function to call when file changes
        """
        if not self._config_file_path:
            raise ConfigError("No configuration file to watch")
        
        # This would use watchdog library in a real implementation
        # For now, just store the callback
        logger.info(f"Watching configuration file: {self._config_file_path}")
        
        # Placeholder implementation
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class ConfigFileHandler(FileSystemEventHandler):
                def on_modified(self, event):
                    if event.src_path == self._config_file_path:
                        callback()
            
            observer = Observer()
            observer.schedule(
                ConfigFileHandler(),
                os.path.dirname(self._config_file_path),
                recursive=False
            )
            observer.start()
            
        except ImportError:
            logger.warning("Watchdog not available, file watching disabled")


def load_configuration(config_path: Optional[str] = None, environment: Optional[str] = None) -> ConfigManager:
    """
    Load application configuration
    
    Args:
        config_path: Path to configuration file
        environment: Environment name
        
    Returns:
        Configured ConfigManager instance
    """
    config_manager = ConfigManager(environment=environment)
    
    if config_path:
        config_manager.load_from_file(config_path)
        config_manager.resolve_environment_variables()
        config_manager.validate_configuration()
    
    return config_manager


# Global configuration manager instance
config_manager: Optional[ConfigManager] = None


def initialize_config_manager(config_path: Optional[str] = None, environment: Optional[str] = None) -> ConfigManager:
    """Initialize global configuration manager instance"""
    global config_manager
    config_manager = load_configuration(config_path=config_path, environment=environment)
    return config_manager


def get_config_manager() -> Optional[ConfigManager]:
    """Get global configuration manager instance"""
    return config_manager