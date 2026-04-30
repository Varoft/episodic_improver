"""Episodic Improver Package"""

from .episodic_improver import (
    FingerprintModel,
    MissionSpec,
    EpisodeMetadata,
    FingerprintIndex,
    RecommendationResult,
)

__all__ = [
    "FingerprintModel",
    "MissionSpec",
    "EpisodeMetadata",
    "FingerprintIndex",
    "RecommendationResult",
]

# 7D System Components (optional)
try:
    from .index_7d_manager import Index7DManager
    from .fingerprint_extractor import FingerprintExtractor
    from .parameter_perturbation import ParameterPerturbation
    from .mission_evaluator import MissionEvaluator
    from .episodic_improver_7d import EpisodicImprover7D

    __all__.extend([
        "Index7DManager",
        "FingerprintExtractor",
        "ParameterPerturbation",
        "MissionEvaluator",
        "EpisodicImprover7D",
    ])
except ImportError:
    pass
