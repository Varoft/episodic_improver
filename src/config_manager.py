#!/usr/bin/env python3
"""
config_manager.py: Configuration management for episodic improver.

Handles loading and validating configuration from TOML files.
Provides sensible defaults and type checking.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python 3.10
    except ImportError:
        tomllib = None


logger = logging.getLogger(__name__)


@dataclass
class DirectoryConfig:
    """Directory paths configuration."""
    episodic_memory_dir: Path = Path("episodic_memory")
    query_dir: Path = Path("etc")
    recommendations_dir: Path = Path("etc/recommendations")
    index_file: Path = Path("etc/fingerprint_index.json")


@dataclass
class MonitoringConfig:
    """Directory monitoring configuration."""
    enabled: bool = True
    ttl_seconds: int = 300  # 5 minutes
    cleanup_interval_seconds: int = 60  # 1 minute
    recursive_watch: bool = True


@dataclass
class FingerprintConfig:
    """Fingerprint model configuration."""
    outcome_quality_threshold: float = 0.70
    k_neighbors: int = 3
    similarity_weights: list = field(default_factory=lambda: [
        0.08, 0.08, 0.12, 0.12, 0.20, 0.10, 0.15, 0.10, 0.05
    ])


@dataclass
class PerturbationConfig:
    """Parameter perturbation strategy configuration."""
    tight_sigma_pct: float = 3.0      # Tight exploitation
    broad_sigma_pct: float = 10.0     # Broad exploration
    tight_threshold: float = 0.95     # Mean similarity > this → tight
    broad_threshold: float = 0.80     # Mean similarity < this → broad


@dataclass
class ParameterRangeConfig:
    """Configuration for a single parameter range."""
    min_val: float
    max_val: float


@dataclass
class ControllerConfig:
    """Controller-specific parameter ranges."""
    goal_tolerance: ParameterRangeConfig = field(
        default_factory=lambda: ParameterRangeConfig(0.05, 0.50)
    )
    max_velocity: ParameterRangeConfig = field(
        default_factory=lambda: ParameterRangeConfig(0.1, 2.0)
    )
    max_angular_velocity: ParameterRangeConfig = field(
        default_factory=lambda: ParameterRangeConfig(0.2, 3.0)
    )
    acceleration: ParameterRangeConfig = field(
        default_factory=lambda: ParameterRangeConfig(0.1, 1.0)
    )
    angular_acceleration: ParameterRangeConfig = field(
        default_factory=lambda: ParameterRangeConfig(0.1, 1.0)
    )


@dataclass
class Config:
    """Complete configuration for episodic improver."""
    directories: DirectoryConfig = field(default_factory=DirectoryConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    fingerprint: FingerprintConfig = field(default_factory=FingerprintConfig)
    perturbation: PerturbationConfig = field(default_factory=PerturbationConfig)
    controller: ControllerConfig = field(default_factory=ControllerConfig)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Config":
        """Create Config from dictionary (loaded from TOML)."""
        config = cls()
        
        # Update directories
        if "directories" in data:
            dir_data = data["directories"]
            config.directories = DirectoryConfig(
                episodic_memory_dir=Path(dir_data.get("episodic_memory_dir", "episodic_memory")),
                query_dir=Path(dir_data.get("query_dir", "etc")),
                recommendations_dir=Path(dir_data.get("recommendations_dir", "etc/recommendations")),
                index_file=Path(dir_data.get("index_file", "etc/fingerprint_index.json")),
            )
        
        # Update monitoring
        if "monitoring" in data:
            mon_data = data["monitoring"]
            config.monitoring = MonitoringConfig(
                enabled=mon_data.get("enabled", True),
                ttl_seconds=mon_data.get("ttl_seconds", 300),
                cleanup_interval_seconds=mon_data.get("cleanup_interval_seconds", 60),
                recursive_watch=mon_data.get("recursive_watch", True),
            )
        
        # Update fingerprint
        if "fingerprint" in data:
            fp_data = data["fingerprint"]
            config.fingerprint = FingerprintConfig(
                outcome_quality_threshold=fp_data.get("outcome_quality_threshold", 0.70),
                k_neighbors=fp_data.get("k_neighbors", 3),
                similarity_weights=fp_data.get("similarity_weights", [
                    0.08, 0.08, 0.12, 0.12, 0.20, 0.10, 0.15, 0.10, 0.05
                ]),
            )
        
        # Update perturbation
        if "perturbation" in data:
            pert_data = data["perturbation"]
            config.perturbation = PerturbationConfig(
                tight_sigma_pct=pert_data.get("tight_sigma_pct", 3.0),
                broad_sigma_pct=pert_data.get("broad_sigma_pct", 10.0),
                tight_threshold=pert_data.get("tight_threshold", 0.95),
                broad_threshold=pert_data.get("broad_threshold", 0.80),
            )
        
        # Update controller parameter ranges
        if "controller" in data:
            ctrl_data = data["controller"]
            
            if "goal_tolerance" in ctrl_data:
                gt = ctrl_data["goal_tolerance"]
                config.controller.goal_tolerance = ParameterRangeConfig(gt["min"], gt["max"])
            
            if "max_velocity" in ctrl_data:
                mv = ctrl_data["max_velocity"]
                config.controller.max_velocity = ParameterRangeConfig(mv["min"], mv["max"])
            
            if "max_angular_velocity" in ctrl_data:
                mav = ctrl_data["max_angular_velocity"]
                config.controller.max_angular_velocity = ParameterRangeConfig(mav["min"], mav["max"])
            
            if "acceleration" in ctrl_data:
                ac = ctrl_data["acceleration"]
                config.controller.acceleration = ParameterRangeConfig(ac["min"], ac["max"])
            
            if "angular_acceleration" in ctrl_data:
                aac = ctrl_data["angular_acceleration"]
                config.controller.angular_acceleration = ParameterRangeConfig(aac["min"], aac["max"])
        
        return config


class ConfigManager:
    """Manages loading and validation of configuration."""
    
    DEFAULT_CONFIG_PATH = Path("etc/config.toml")
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to TOML config file. Uses default if None.
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = Config()  # Default config
        
        logger.info(f"ConfigManager initialized with path: {self.config_path}")
    
    def load(self) -> bool:
        """
        Load configuration from TOML file.
        
        Returns:
            True if loaded successfully, False if file doesn't exist (uses defaults).
        """
        if not self.config_path.exists():
            logger.info(
                f"Config file not found: {self.config_path}. "
                f"Using default configuration."
            )
            return False
        
        if tomllib is None:
            logger.warning(
                "tomllib not available (Python <3.11). "
                "Install 'tomli' for TOML support: pip install tomli"
            )
            return False
        
        try:
            with open(self.config_path, 'rb') as f:
                data = tomllib.load(f)
            
            self.config = Config.from_dict(data)
            logger.info(f"✓ Loaded configuration from {self.config_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            logger.info("Using default configuration")
            return False
    
    def get(self) -> Config:
        """Get current configuration."""
        return self.config
    
    def to_dict(self) -> Dict:
        """Export configuration to dictionary."""
        return {
            "directories": {
                "episodic_memory_dir": str(self.config.directories.episodic_memory_dir),
                "query_dir": str(self.config.directories.query_dir),
                "recommendations_dir": str(self.config.directories.recommendations_dir),
                "index_file": str(self.config.directories.index_file),
            },
            "monitoring": {
                "enabled": self.config.monitoring.enabled,
                "ttl_seconds": self.config.monitoring.ttl_seconds,
                "cleanup_interval_seconds": self.config.monitoring.cleanup_interval_seconds,
                "recursive_watch": self.config.monitoring.recursive_watch,
            },
            "fingerprint": {
                "outcome_quality_threshold": self.config.fingerprint.outcome_quality_threshold,
                "k_neighbors": self.config.fingerprint.k_neighbors,
                "similarity_weights": self.config.fingerprint.similarity_weights,
            },
            "perturbation": {
                "tight_sigma_pct": self.config.perturbation.tight_sigma_pct,
                "broad_sigma_pct": self.config.perturbation.broad_sigma_pct,
                "tight_threshold": self.config.perturbation.tight_threshold,
                "broad_threshold": self.config.perturbation.broad_threshold,
            },
            "controller": {
                "goal_tolerance": {
                    "min": self.config.controller.goal_tolerance.min_val,
                    "max": self.config.controller.goal_tolerance.max_val,
                },
                "max_velocity": {
                    "min": self.config.controller.max_velocity.min_val,
                    "max": self.config.controller.max_velocity.max_val,
                },
                "max_angular_velocity": {
                    "min": self.config.controller.max_angular_velocity.min_val,
                    "max": self.config.controller.max_angular_velocity.max_val,
                },
                "acceleration": {
                    "min": self.config.controller.acceleration.min_val,
                    "max": self.config.controller.acceleration.max_val,
                },
                "angular_acceleration": {
                    "min": self.config.controller.angular_acceleration.min_val,
                    "max": self.config.controller.angular_acceleration.max_val,
                },
            }
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test default config
    mgr = ConfigManager()
    mgr.load()
    
    cfg = mgr.get()
    print("\nConfiguration loaded:")
    print(f"  Outcome quality threshold: {cfg.fingerprint.outcome_quality_threshold}")
    print(f"  k-Neighbors: {cfg.fingerprint.k_neighbors}")
    print(f"  TTL: {cfg.monitoring.ttl_seconds}s")
    print(f"  Max velocity range: [{cfg.controller.max_velocity.min_val}, {cfg.controller.max_velocity.max_val}]")
