#!/usr/bin/env python3
"""
test_config.py: Tests for configuration management (Phase 3).
"""

import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config_manager import ConfigManager, Config, ParameterRangeConfig


class TestConfigManager:
    """Test configuration loading and validation."""
    
    def test_default_config(self):
        """Test that default config is used when no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "nonexistent.toml"
            mgr = ConfigManager(config_file)
            result = mgr.load()
            
            assert not result, "Should return False when file doesn't exist"
            config = mgr.get()
            
            # Check defaults
            assert config.fingerprint.outcome_quality_threshold == 0.70
            assert config.fingerprint.k_neighbors == 3
            assert config.monitoring.ttl_seconds == 300
            assert len(config.fingerprint.similarity_weights) == 9
    
    def test_parameter_range(self):
        """Test ParameterRangeConfig structure."""
        param_range = ParameterRangeConfig(min_val=0.1, max_val=2.0)
        
        assert param_range.min_val == 0.1
        assert param_range.max_val == 2.0
    
    def test_config_controller_ranges(self):
        """Test controller parameter ranges are initialized correctly."""
        config = Config()
        
        assert config.controller.goal_tolerance.min_val == 0.05
        assert config.controller.goal_tolerance.max_val == 0.50
        assert config.controller.max_velocity.min_val == 0.1
        assert config.controller.max_velocity.max_val == 2.0
    
    def test_config_to_dict(self):
        """Test configuration export to dictionary."""
        mgr = ConfigManager()
        mgr.load()
        
        config_dict = mgr.to_dict()
        
        # Check structure
        assert "directories" in config_dict
        assert "monitoring" in config_dict
        assert "fingerprint" in config_dict
        assert "perturbation" in config_dict
        assert "controller" in config_dict
        
        # Check some values
        assert config_dict["fingerprint"]["k_neighbors"] == 3
        assert config_dict["monitoring"]["ttl_seconds"] == 300
        assert config_dict["controller"]["max_velocity"]["max"] == 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
