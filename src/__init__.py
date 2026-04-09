"""Episodic Improver Package"""

from .episodic_improver import (
    FingerprintModel,
    MissionSpec,
    EpisodeMetadata,
    FingerprintIndex,
    RecommendationResult,
)
from .directory_monitor import DirectoryMonitor, MonitorConfig
from .recommendation_engine import RecommendationEngine, RecommendationEngineConfig
from .main import EpisodicImproverComponent

# 7D System Components
try:
    from .index_7d_manager import Index7DManager
    from .fingerprint_extractor import FingerprintExtractor
    from .parameter_perturbation import ParameterPerturbation
    from .mission_evaluator import MissionEvaluator
    from .episodic_improver_7d import EpisodicImprover7D
    _7D_AVAILABLE = True
except ImportError:
    _7D_AVAILABLE = False

__all__ = [
    "FingerprintModel",
    "MissionSpec",
    "EpisodeMetadata",
    "FingerprintIndex",
    "RecommendationResult",
    "DirectoryMonitor",
    "MonitorConfig",
    "RecommendationEngine",
    "RecommendationEngineConfig",
    "EpisodicImproverComponent",
]

if _7D_AVAILABLE:
    __all__.extend([
        "Index7DManager",
        "FingerprintExtractor",
        "ParameterPerturbation",
        "MissionEvaluator",
        "EpisodicImprover7D",
    ])
