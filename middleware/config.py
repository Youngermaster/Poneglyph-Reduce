#!/usr/bin/env python3
"""
Configuration module for Poneglyph-Reduce middleware
Centralized configuration to avoid code duplication
"""

import os
from pathlib import Path
from typing import Optional

# Project paths
REPO_ROOT = Path(__file__).parent.parent
MIDDLEWARE_DIR = REPO_ROOT / "middleware"
GENERATED_DIR = MIDDLEWARE_DIR / "generated"
PROTO_PATH = REPO_ROOT / "Road-Poneglyph" / "src" / "main" / "proto" / "poneglyph.proto"

# Default configuration
DEFAULT_CONFIG = {
    # Server ports
    "GRPC_PORT": 50051,
    "METRICS_HTTP_PORT": 8080,
    "FAULT_TOLERANCE_API_PORT": 8083,
    
    # Fault tolerance settings
    "DEFAULT_TASK_TIMEOUT": 300,  # 5 minutes
    "MAX_RETRIES": 3,
    "CIRCUIT_BREAKER_FAILURE_THRESHOLD": 5,
    "CIRCUIT_BREAKER_RECOVERY_TIMEOUT": 60,
    
    # Load balancer settings
    "DEFAULT_LOAD_BALANCING_STRATEGY": "smart_composite",
    
    # Monitoring settings
    "METRICS_COLLECTION_INTERVAL": 5,
    "HEALTH_CHECK_INTERVAL": 10,
    
    # Database settings
    "USE_DYNAMODB": False,
    "DYNAMODB_TABLE_NAME": "poneglyph-state",
    "DYNAMODB_REGION": "us-east-1",
    
    # S3 settings
    "S3_BUCKET": None,
    "S3_REGION": "us-east-1",
    
    # MQTT settings
    "MQTT_ENABLED": True,
    "MQTT_BROKER": "localhost",
    "MQTT_PORT": 1883,
}


class Config:
    """Configuration management class"""
    
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        env_mappings = {
            "GRPC_PORT": ("PONEGLYPH_GRPC_PORT", int),
            "METRICS_HTTP_PORT": ("PONEGLYPH_METRICS_PORT", int),
            "FAULT_TOLERANCE_API_PORT": ("PONEGLYPH_FT_API_PORT", int),
            "DEFAULT_TASK_TIMEOUT": ("PONEGLYPH_TASK_TIMEOUT", int),
            "MAX_RETRIES": ("PONEGLYPH_MAX_RETRIES", int),
            "USE_DYNAMODB": ("PONEGLYPH_USE_DYNAMODB", lambda x: x.lower() == 'true'),
            "DYNAMODB_TABLE_NAME": ("PONEGLYPH_DYNAMODB_TABLE", str),
            "DYNAMODB_REGION": ("AWS_REGION", str),
            "S3_BUCKET": ("S3_BUCKET", str),
            "S3_REGION": ("AWS_REGION", str),
            "MQTT_BROKER": ("PONEGLYPH_MQTT_BROKER", str),
            "MQTT_PORT": ("PONEGLYPH_MQTT_PORT", int),
        }
        
        for config_key, (env_var, converter) in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    self._config[config_key] = converter(env_value)
                except (ValueError, TypeError):
                    print(f"Warning: Invalid value for {env_var}: {env_value}")
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        """Set configuration value"""
        self._config[key] = value
    
    def get_all(self) -> dict:
        """Get all configuration"""
        return self._config.copy()
    
    @property
    def grpc_port(self) -> int:
        return self.get("GRPC_PORT")
    
    @property
    def metrics_port(self) -> int:
        return self.get("METRICS_HTTP_PORT")
    
    @property
    def fault_tolerance_api_port(self) -> int:
        return self.get("FAULT_TOLERANCE_API_PORT")
    
    @property
    def use_dynamodb(self) -> bool:
        return self.get("USE_DYNAMODB")
    
    @property
    def s3_bucket(self) -> Optional[str]:
        return self.get("S3_BUCKET")
    
    @property
    def mqtt_enabled(self) -> bool:
        return self.get("MQTT_ENABLED")


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get global configuration instance"""
    return config