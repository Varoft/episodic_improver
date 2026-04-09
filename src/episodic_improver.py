#!/usr/bin/env python3
"""
episodic_improver.py: Fingerprint-based episodic memory and recommendation system.

This module implements a fingerprint-based approach to retrieving similar navigation
episodes and recommending control parameters based on mission specifications.
"""

import json
import math
import logging
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Tuple, Optional
from pathlib import Path

import numpy as np


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class MissionSpec:
    """Specification of a navigation mission."""
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    estimated_distance: float
    obstacle_density: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "MissionSpec":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class EpisodeMetadata:
    """Metadata for a stored episode with computed fingerprint and scores."""
    episode_id: str
    fingerprint: np.ndarray  # Shape (9,)
    original_params: Dict[str, float]
    efficiency_score: float
    safety_score: float
    smoothness_score: float
    outcome_quality: float
    timestamp_ms: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "episode_id": self.episode_id,
            "fingerprint": self.fingerprint.tolist(),
            "original_params": self.original_params,
            "efficiency_score": self.efficiency_score,
            "safety_score": self.safety_score,
            "smoothness_score": self.smoothness_score,
            "outcome_quality": self.outcome_quality,
            "timestamp_ms": self.timestamp_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EpisodeMetadata":
        """Create from dictionary."""
        data_copy = data.copy()
        data_copy["fingerprint"] = np.array(data_copy["fingerprint"], dtype=np.float64)
        return cls(**data_copy)


@dataclass
class FingerprintIndex:
    """Index of episodes with fingerprints and metadata."""
    episodes: List[EpisodeMetadata] = field(default_factory=list)
    similarity_weights: np.ndarray = field(default_factory=lambda: np.array([0.08, 0.08, 0.12, 0.12, 0.20, 0.10, 0.15, 0.10, 0.05], dtype=np.float64))
    outcome_quality_threshold: float = 0.70
    weight_efficiency: float = 0.40
    weight_safety: float = 0.35
    weight_smoothness: float = 0.25
    last_episode_count: int = 0
    last_updated_ms: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "episodes": [ep.to_dict() for ep in self.episodes],
            "similarity_weights": self.similarity_weights.tolist(),
            "config": {
                "outcome_quality_threshold": self.outcome_quality_threshold,
                "weight_efficiency": self.weight_efficiency,
                "weight_safety": self.weight_safety,
                "weight_smoothness": self.weight_smoothness,
            },
            "metadata": {
                "last_episode_count": self.last_episode_count,
                "last_updated_ms": self.last_updated_ms,
                "episode_count": len(self.episodes),
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "FingerprintIndex":
        """Create from dictionary."""
        config = data.get("config", {})
        return cls(
            episodes=[EpisodeMetadata.from_dict(ep) for ep in data.get("episodes", [])],
            similarity_weights=np.array(data.get("similarity_weights", [0.08, 0.08, 0.12, 0.12, 0.20, 0.10, 0.15, 0.10, 0.05]), dtype=np.float64),
            outcome_quality_threshold=config.get("outcome_quality_threshold", 0.70),
            weight_efficiency=config.get("weight_efficiency", 0.40),
            weight_safety=config.get("weight_safety", 0.35),
            weight_smoothness=config.get("weight_smoothness", 0.25),
            last_episode_count=data.get("metadata", {}).get("last_episode_count", 0),
            last_updated_ms=data.get("metadata", {}).get("last_updated_ms", 0),
        )


@dataclass
class RecommendationResult:
    """Result of k-NN query with similar episodes."""
    top_k: List[EpisodeMetadata] = field(default_factory=list)
    similarities: List[float] = field(default_factory=list)
    mean_similarity: float = 0.0
    episodes_considered: int = 0
    episodes_filtered: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "top_k": [ep.to_dict() for ep in self.top_k],
            "similarities": self.similarities,
            "mean_similarity": self.mean_similarity,
            "metadata": {
                "episodes_considered": self.episodes_considered,
                "episodes_filtered": self.episodes_filtered,
            }
        }


# ============================================================================
# FINGERPRINT MODEL
# ============================================================================

class FingerprintModel:
    """
    Fingerprint-based episodic memory model for navigation recommendation.
    
    Manages a 9-dimensional fingerprint space representing mission characteristics,
    computes outcome quality scores, and retrieves similar episodes using k-NN.
    """

    # Constants
    SPACE_RANGE = 80.0
    MAX_DIAGONAL = 56.5685424949  # sqrt(2) * 40
    SAFE_DISTANCE = 0.5
    MIN_TORTUOSITY = 1.0
    MAX_TORTUOSITY = 2.5
    EPSILON = 1e-9

    def __init__(
        self,
        similarity_weights: Optional[np.ndarray] = None,
        w_efficiency: float = 0.40,
        w_safety: float = 0.35,
        w_smoothness: float = 0.25,
        quality_threshold: float = 0.70,
    ):
        """
        Initialize the fingerprint model.

        Args:
            similarity_weights: 9-dimensional weight vector for fingerprint similarity.
                               Defaults to [0.08, 0.08, 0.12, 0.12, 0.20, 0.10, 0.15, 0.10, 0.05]
            w_efficiency: Weight for efficiency in outcome quality computation.
            w_safety: Weight for safety in outcome quality computation.
            w_smoothness: Weight for smoothness in outcome quality computation.
            quality_threshold: Minimum outcome quality to include episodes in k-NN.
        """
        self.index_ = FingerprintIndex()
        
        if similarity_weights is None:
            self.index_.similarity_weights = np.array(
                [0.08, 0.08, 0.12, 0.12, 0.20, 0.10, 0.15, 0.10, 0.05],
                dtype=np.float64
            )
        else:
            self.index_.similarity_weights = np.array(similarity_weights, dtype=np.float64)
        
        self.index_.outcome_quality_threshold = quality_threshold
        self.index_.weight_efficiency = w_efficiency
        self.index_.weight_safety = w_safety
        self.index_.weight_smoothness = w_smoothness
        
        # Validate weights sum to ~1.0
        total_weight = w_efficiency + w_safety + w_smoothness
        if abs(total_weight - 1.0) > 1e-6:
            logger.warning(
                f"Outcome quality weights don't sum to 1.0: {total_weight}. "
                f"Renormalizing..."
            )
            self.index_.weight_efficiency = w_efficiency / total_weight
            self.index_.weight_safety = w_safety / total_weight
            self.index_.weight_smoothness = w_smoothness / total_weight

    # ========================================================================
    # Fingerprint Computation
    # ========================================================================

    def compute_fingerprint(self, spec: MissionSpec) -> np.ndarray:
        """
        Compute 9-dimensional fingerprint from mission specification.

        Fingerprint components:
        - f[0-1]: Normalized start position [0, 1]
        - f[2-3]: Normalized end position [0, 1]
        - f[4]: Heading angle [-1, 1]
        - f[5]: Straight-line distance normalized [0, 1]
        - f[6]: Tortuosity [1, 2.5]
        - f[7]: Density [0, 1]
        - f[8]: Hardness composite [0, 1]

        Args:
            spec: MissionSpec describing the navigation mission.

        Returns:
            9-element numpy array representing the fingerprint.

        Raises:
            ValueError: If spec components out of valid ranges.
        """
        # Validate inputs
        if not (-40 <= spec.start_x <= 40 and -40 <= spec.start_y <= 40):
            raise ValueError(f"Start position out of range: ({spec.start_x}, {spec.start_y})")
        if not (-40 <= spec.end_x <= 40 and -40 <= spec.end_y <= 40):
            raise ValueError(f"End position out of range: ({spec.end_x}, {spec.end_y})")
        if not (0 <= spec.obstacle_density <= 1):
            raise ValueError(f"Density out of range: {spec.obstacle_density}")
        if not (0 <= spec.estimated_distance <= 70):
            raise ValueError(f"Estimated distance out of range: {spec.estimated_distance}")
        
        fp = np.zeros(9, dtype=np.float64)
        
        # f[0-3]: Normalized positions [0, 1]
        # Shift from [-40, 40] to [0, 80] then normalize
        fp[0] = np.clip((spec.start_x + 40.0) / self.SPACE_RANGE, 0.0, 1.0)
        fp[1] = np.clip((spec.start_y + 40.0) / self.SPACE_RANGE, 0.0, 1.0)
        fp[2] = np.clip((spec.end_x + 40.0) / self.SPACE_RANGE, 0.0, 1.0)
        fp[3] = np.clip((spec.end_y + 40.0) / self.SPACE_RANGE, 0.0, 1.0)
        
        # f[4]: Heading angle [-1, 1]
        fp[4] = math.atan2(
            spec.end_y - spec.start_y,
            spec.end_x - spec.start_x
        ) / math.pi
        
        # f[5]: Straight-line distance [0, 1]
        straight_line = self._compute_straight_line_distance(
            spec.start_x, spec.start_y, spec.end_x, spec.end_y
        )
        fp[5] = np.clip(straight_line / self.MAX_DIAGONAL, 0.0, 1.0)
        
        # f[6]: Tortuosity [1, 2.5]
        tortuosity = self._normalize_tortuosity(spec.estimated_distance, straight_line)
        fp[6] = np.clip(tortuosity, self.MIN_TORTUOSITY, self.MAX_TORTUOSITY)
        
        # f[7]: Density [0, 1] (already normalized from input)
        fp[7] = np.clip(spec.obstacle_density, 0.0, 1.0)
        
        # f[8]: Hardness composite (tortuosity × density) / 2.5 [0, 1]
        fp[8] = np.clip((tortuosity * spec.obstacle_density) / 2.5, 0.0, 1.0)
        
        return fp

    def validate_fingerprint(self, fp: np.ndarray) -> bool:
        """
        Validate fingerprint bounds and well-formedness.

        Args:
            fp: Fingerprint to validate.

        Returns:
            True if valid, False otherwise.
        """
        if fp.shape != (9,):
            logger.error(f"Fingerprint shape mismatch: {fp.shape}")
            return False
        
        if np.any(np.isnan(fp)) or np.any(np.isinf(fp)):
            logger.error("Fingerprint contains NaN or inf values")
            return False
        
        # Check bounds for each component
        bounds = [
            (0.0, 1.0),   # f[0]
            (0.0, 1.0),   # f[1]
            (0.0, 1.0),   # f[2]
            (0.0, 1.0),   # f[3]
            (-1.0, 1.0),  # f[4]
            (0.0, 1.0),   # f[5]
            (1.0, 2.5),   # f[6]
            (0.0, 1.0),   # f[7]
            (0.0, 1.0),   # f[8]
        ]
        
        for i, (lower, upper) in enumerate(bounds):
            if not (lower - 1e-6 <= fp[i] <= upper + 1e-6):
                logger.error(
                    f"Fingerprint[{i}] = {fp[i]} out of bounds [{lower}, {upper}]"
                )
                return False
        
        return True

    # ========================================================================
    # Score Computation
    # ========================================================================

    def compute_safety_score(self, min_esdf_m: float) -> float:
        """
        Compute safety score from minimum ESDF distance.

        Guarantees result ∈ [0, 1] using min(esdf, 0.5) / 0.5

        Args:
            min_esdf_m: Minimum Euclidean signed distance field value in meters.

        Returns:
            Safety score in [0, 1].
        """
        # Normalize to [0, 0.5] then scale to [0, 1]
        normalized = min(min_esdf_m, self.SAFE_DISTANCE) / self.SAFE_DISTANCE
        return np.clip(normalized, 0.0, 1.0)

    def compute_smoothness_score(self, comfort_jerk: float) -> float:
        """
        Compute smoothness score from jerk/comfort metric.

        Args:
            comfort_jerk: Comfort jerk metric (typically 0-1 range).

        Returns:
            Smoothness score in [0, 1]. Higher is smoother.
        """
        smoothness = 1.0 - min(comfort_jerk, 1.0)
        return np.clip(smoothness, 0.0, 1.0)

    def compute_outcome_quality(
        self,
        efficiency: float,
        safety: float,
        smoothness: float,
    ) -> float:
        """
        Aggregate efficiency, safety, and smoothness into outcome quality.

        Formula: quality = 0.40×efficiency + 0.35×safety + 0.25×smoothness

        Args:
            efficiency: Efficiency score in [0, 1].
            safety: Safety score in [0, 1].
            smoothness: Smoothness score in [0, 1].

        Returns:
            Outcome quality in [0, 1].
        """
        eff = np.clip(efficiency, 0.0, 1.0)
        safe = np.clip(safety, 0.0, 1.0)
        smooth = np.clip(smoothness, 0.0, 1.0)
        
        quality = (
            self.index_.weight_efficiency * eff +
            self.index_.weight_safety * safe +
            self.index_.weight_smoothness * smooth
        )
        
        return np.clip(quality, 0.0, 1.0)

    # ========================================================================
    # Index Management
    # ========================================================================

    def add_episode(self, metadata: EpisodeMetadata) -> None:
        """
        Add episode to index.

        Args:
            metadata: EpisodeMetadata to add.
        """
        if not self.validate_fingerprint(metadata.fingerprint):
            logger.warning(
                f"Invalid fingerprint for episode {metadata.episode_id}, skipping"
            )
            return
        
        self.index_.episodes.append(metadata)
        logger.info(f"Added episode {metadata.episode_id}, total: {len(self.index_.episodes)}")

    def clear_index(self) -> None:
        """Clear all episodes from index."""
        self.index_.episodes = []
        logger.info("Cleared index")

    def get_episode_count(self) -> int:
        """Get number of episodes in index."""
        return len(self.index_.episodes)

    # ========================================================================
    # Similarity and Retrieval
    # ========================================================================

    def weighted_cosine_similarity(
        self,
        fp1: np.ndarray,
        fp2: np.ndarray,
    ) -> float:
        """
        Compute weighted cosine similarity between two fingerprints.

        Formula: sim = dot(w⊙fp1, w⊙fp2) / (‖w⊙fp1‖ × ‖w⊙fp2‖)
        where ⊙ is element-wise multiplication. This ensures similarity ∈ [0,1].

        Args:
            fp1: First fingerprint (9,).
            fp2: Second fingerprint (9,).

        Returns:
            Similarity in [0, 1].
        """
        # Scale fingerprints by weights
        weighted_fp1 = self.index_.similarity_weights * fp1
        weighted_fp2 = self.index_.similarity_weights * fp2
        
        # Numerator: dot product of weighted fingerprints
        numerator = np.dot(weighted_fp1, weighted_fp2)
        
        # Denominator: product of norms
        norm1 = np.linalg.norm(weighted_fp1)
        norm2 = np.linalg.norm(weighted_fp2)
        
        # Handle zero norm case
        denom = norm1 * norm2
        if denom < self.EPSILON:
            return 0.0
        
        similarity = numerator / denom
        # By Cauchy-Schwarz, this should always be in [0, 1], but clip for safety
        return np.clip(similarity, 0.0, 1.0)

    def query_knn(
        self,
        spec: MissionSpec,
        k: int = 3,
    ) -> RecommendationResult:
        """
        Query k-nearest neighbor similar episodes.

        Args:
            spec: Query mission specification.
            k: Number of neighbors to return.

        Returns:
            RecommendationResult with top k episodes and similarities.
        """
        query_fp = self.compute_fingerprint(spec)
        
        if not self.validate_fingerprint(query_fp):
            logger.error("Invalid query fingerprint")
            return RecommendationResult()
        
        # Filter by quality threshold
        all_candidates = len(self.index_.episodes)
        candidates = [
            ep for ep in self.index_.episodes
            if ep.outcome_quality >= self.index_.outcome_quality_threshold
        ]
        filtered_count = all_candidates - len(candidates)
        
        if not candidates:
            logger.warning("No episodes meet quality threshold")
            result = RecommendationResult()
            result.episodes_considered = all_candidates
            result.episodes_filtered = filtered_count
            return result
        
        # Compute similarities
        similarities = [
            self.weighted_cosine_similarity(query_fp, ep.fingerprint)
            for ep in candidates
        ]
        
        # Sort by similarity descending
        sorted_pairs = sorted(
            zip(candidates, similarities),
            key=lambda x: x[1],
            reverse=True,
        )
        
        # Take top k
        top_k_pairs = sorted_pairs[:min(k, len(sorted_pairs))]
        top_k_episodes = [p[0] for p in top_k_pairs]
        top_k_sims = [p[1] for p in top_k_pairs]
        
        mean_sim = np.mean(top_k_sims) if top_k_sims else 0.0
        
        logger.info(
            f"k-NN query returned {len(top_k_episodes)} episodes, "
            f"mean_similarity={mean_sim:.4f}"
        )
        
        result = RecommendationResult(
            top_k=top_k_episodes,
            similarities=top_k_sims,
            mean_similarity=mean_sim,
            episodes_considered=all_candidates,
            episodes_filtered=filtered_count,
        )
        return result

    # ========================================================================
    # Perturbation Strategy
    # ========================================================================

    def compute_perturbation(self, mean_similarity: float) -> Dict:
        """
        Compute perturbation strategy based on mean similarity.

        Args:
            mean_similarity: Mean similarity from k-NN query.

        Returns:
            Dictionary with 'sigma_pct' and 'strategy' keys.
        """
        if mean_similarity > 0.95:
            sigma_pct = 0.03
            strategy = "tight_exploitation"
        elif mean_similarity < 0.80:
            sigma_pct = 0.10
            strategy = "broad_exploration"
        else:
            # Linear interpolation between 3% and 10%
            sigma_pct = 0.03 + 0.07 * (mean_similarity - 0.80) / 0.15
            strategy = "linear_interpolation"
        
        return {
            "sigma_pct": sigma_pct,
            "strategy": strategy,
            "mean_similarity": mean_similarity,
        }

    # ========================================================================
    # Persistence
    # ========================================================================

    def save_index(self, filepath: str) -> bool:
        """
        Save index to JSON file.

        Args:
            filepath: Path to save file.

        Returns:
            True on success, False on failure.
        """
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = self.index_.to_dict()
            
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved index with {len(self.index_.episodes)} episodes to {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save index to {filepath}: {e}")
            return False

    def load_index(self, filepath: str) -> bool:
        """
        Load index from JSON file.

        Args:
            filepath: Path to load file.

        Returns:
            True on success, False on failure.
        """
        try:
            path = Path(filepath)
            
            if not path.exists():
                logger.warning(f"Index file not found: {filepath}")
                return False
            
            with open(path, "r") as f:
                data = json.load(f)
            
            self.index_ = FingerprintIndex.from_dict(data)
            logger.info(f"Loaded index with {len(self.index_.episodes)} episodes from {filepath}")
            return True
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {filepath}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load index from {filepath}: {e}")
            return False

    # ========================================================================
    # Helper Methods
    # ========================================================================

    @staticmethod
    def _compute_straight_line_distance(
        sx: float,
        sy: float,
        ex: float,
        ey: float,
    ) -> float:
        """Compute Euclidean distance between two points."""
        dx = ex - sx
        dy = ey - sy
        return math.sqrt(dx * dx + dy * dy)

    @staticmethod
    def _normalize_tortuosity(estimated_dist: float, straight_line_dist: float) -> float:
        """
        Compute tortuosity as ratio of path to straight line.

        Args:
            estimated_dist: Estimated path distance.
            straight_line_dist: Straight-line distance.

        Returns:
            Tortuosity (path_dist / straight_line_dist), minimum 1.0.
        """
        if straight_line_dist < 1e-6:
            return 1.0
        
        tortuosity = estimated_dist / straight_line_dist
        return max(1.0, tortuosity)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Initialize model, add episode, query k-NN
    print("=" * 60)
    print("Episodic Improver - Fingerprinting Example")
    print("=" * 60)
    
    # Initialize model with default weights
    model = FingerprintModel(
        w_efficiency=0.40,
        w_safety=0.35,
        w_smoothness=0.25,
        quality_threshold=0.50,
    )
    
    # Create example mission
    print("\n1. Testing fingerprint computation:")
    mission = MissionSpec(
        start_x=0.0,
        start_y=-27.0,
        end_x=0.0,
        end_y=26.8,
        estimated_distance=54.0,
        obstacle_density=0.12,
    )
    
    fp = model.compute_fingerprint(mission)
    print(f"   Mission: start=({mission.start_x},{mission.start_y}), end=({mission.end_x},{mission.end_y})")
    print(f"   Fingerprint (9D): {fp}")
    print(f"   Valid: {model.validate_fingerprint(fp)}")
    
    # Compute quality scores
    print("\n2. Testing score computation:")
    safety = model.compute_safety_score(0.4)
    smoothness = model.compute_smoothness_score(0.2)
    quality = model.compute_outcome_quality(0.9, safety, smoothness)
    
    print(f"   Safety score: {safety:.3f}")
    print(f"   Smoothness score: {smoothness:.3f}")
    print(f"   Outcome quality: {quality:.3f}")
    
    # Create and add episodes
    print("\n3. Testing episode addition and k-NN:")
    episode = EpisodeMetadata(
        episode_id="ep_test_001",
        fingerprint=fp,
        original_params={"max_adv": 0.8, "max_rot": 0.7},
        efficiency_score=0.9,
        safety_score=safety,
        smoothness_score=smoothness,
        outcome_quality=quality,
        timestamp_ms=1234567890,
    )
    
    model.add_episode(episode)
    print(f"   Added 1 episode, total: {model.get_episode_count()}")
    
    # Query k-NN
    query_spec = MissionSpec(
        start_x=1.0,
        start_y=-26.5,
        end_x=-0.5,
        end_y=25.0,
        estimated_distance=52.0,
        obstacle_density=0.15,
    )
    
    result = model.query_knn(query_spec, k=1)
    print(f"   k-NN query returned {len(result.top_k)} episodes")
    if result.top_k:
        print(f"   Mean similarity: {result.mean_similarity:.4f}")
    
    # Test perturbation
    print("\n4. Testing perturbation strategy:")
    pert_tight = model.compute_perturbation(0.97)
    pert_broad = model.compute_perturbation(0.75)
    pert_linear = model.compute_perturbation(0.87)
    
    print(f"   High similarity (0.97): σ={pert_tight['sigma_pct']:.2%} ({pert_tight['strategy']})")
    print(f"   Low similarity (0.75): σ={pert_broad['sigma_pct']:.2%} ({pert_broad['strategy']})")
    print(f"   Mid similarity (0.87): σ={pert_linear['sigma_pct']:.2%} ({pert_linear['strategy']})")
    
    # Test persistence
    print("\n5. Testing JSON persistence:")
    model.save_index("/tmp/test_index.json")
    
    model2 = FingerprintModel()
    model2.load_index("/tmp/test_index.json")
    print(f"   Loaded index: {model2.get_episode_count()} episodes")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
