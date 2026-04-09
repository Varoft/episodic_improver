#!/usr/bin/env python3
"""
Unit tests for episodic_improver fingerprinting module.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from episodic_improver import (
    FingerprintModel,
    MissionSpec,
    EpisodeMetadata,
    FingerprintIndex,
    RecommendationResult,
)


class TestFingerprintComputation:
    """Test fingerprint 9D vector computation."""

    def test_fingerprint_shape(self):
        """Test that fingerprint has correct shape."""
        model = FingerprintModel()
        spec = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=10.0,
            estimated_distance=20.0,
            obstacle_density=0.5,
        )
        fp = model.compute_fingerprint(spec)
        assert fp.shape == (9,), f"Expected shape (9,), got {fp.shape}"

    def test_fingerprint_dtype(self):
        """Test that fingerprint is float64."""
        model = FingerprintModel()
        spec = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=10.0,
            estimated_distance=20.0,
            obstacle_density=0.5,
        )
        fp = model.compute_fingerprint(spec)
        assert fp.dtype == np.float64

    def test_fingerprint_bounds(self):
        """Test that all fingerprint components are within valid bounds."""
        model = FingerprintModel()
        spec = MissionSpec(
            start_x=-40.0, start_y=-40.0,
            end_x=40.0, end_y=40.0,
            estimated_distance=70.0,
            obstacle_density=1.0,
        )
        fp = model.compute_fingerprint(spec)
        
        # f[0-3, 5, 7, 8] in [0, 1]
        for i in [0, 1, 2, 3, 5, 7, 8]:
            assert 0.0 <= fp[i] <= 1.0, f"fp[{i}] = {fp[i]} out of [0, 1]"
        
        # f[4] (heading) in [-1, 1]
        assert -1.0 <= fp[4] <= 1.0, f"fp[4] = {fp[4]} out of [-1, 1]"
        
        # f[6] (tortuosity) in [1, 2.5]
        assert 1.0 <= fp[6] <= 2.5, f"fp[6] = {fp[6]} out of [1, 2.5]"

    def test_normalizations(self):
        """Test normalization of individual components."""
        model = FingerprintModel()
        
        # Start at origin
        spec_origin = MissionSpec(
            start_x=-40.0, start_y=-40.0,
            end_x=-40.0, end_y=-40.0,
            estimated_distance=0.0,
            obstacle_density=0.0,
        )
        fp_origin = model.compute_fingerprint(spec_origin)
        
        # Start at center
        spec_center = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=0.0, end_y=0.0,
            estimated_distance=0.0,
            obstacle_density=0.0,
        )
        fp_center = model.compute_fingerprint(spec_center)
        
        # Origin: (-40, -40) → [0, 0]
        assert fp_origin[0] == 0.0, "f[0] at origin should be 0.0"
        assert fp_origin[1] == 0.0, "f[1] at origin should be 0.0"
        
        # Center: (0, 0) → [0.5, 0.5]
        assert 0.49 < fp_center[0] < 0.51, "f[0] at center should be ~0.5"
        assert 0.49 < fp_center[1] < 0.51, "f[1] at center should be ~0.5"

    def test_heading_angle(self):
        """Test heading angle computation."""
        model = FingerprintModel()
        
        # Heading right (0 degrees → 0)
        spec_right = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=0.0,
            estimated_distance=10.0,
            obstacle_density=0.0,
        )
        fp_right = model.compute_fingerprint(spec_right)
        assert 0.0 - 0.1 < fp_right[4] < 0.0 + 0.1, "Heading right should be near 0"
        
        # Heading up (90 degrees → π/2 / π = 0.5)
        spec_up = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=0.0, end_y=10.0,
            estimated_distance=10.0,
            obstacle_density=0.0,
        )
        fp_up = model.compute_fingerprint(spec_up)
        assert 0.45 < fp_up[4] < 0.55, "Heading up (90°) should be 0.5"

    def test_tortuosity(self):
        """Test tortuosity computation."""
        model = FingerprintModel()
        
        # Straight path: est_dist = straight_line → tortuosity = 1
        spec_straight = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=0.0,
            estimated_distance=10.0,
            obstacle_density=0.0,
        )
        fp_straight = model.compute_fingerprint(spec_straight)
        assert fp_straight[6] == 1.0, "Straight path should have tortuosity = 1"
        
        # Winding path: est_dist = 2 * straight_line → tortuosity = 2
        spec_winding = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=0.0,
            estimated_distance=20.0,
            obstacle_density=0.0,
        )
        fp_winding = model.compute_fingerprint(spec_winding)
        assert fp_winding[6] == 2.0, "Winding path should have tortuosity = 2"


class TestFingerprintValidation:
    """Test fingerprint validation."""

    def test_validate_valid_fingerprint(self):
        """Test that valid fingerprints pass validation."""
        model = FingerprintModel()
        spec = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=10.0,
            estimated_distance=20.0,
            obstacle_density=0.5,
        )
        fp = model.compute_fingerprint(spec)
        assert model.validate_fingerprint(fp), "Valid fingerprint should pass validation"

    def test_validate_invalid_shape(self):
        """Test validation rejects wrong shape."""
        model = FingerprintModel()
        fp = np.array([0.5, 0.5, 0.5], dtype=np.float64)  # Shape (3,) instead of (9,)
        assert not model.validate_fingerprint(fp), "Wrong shape should fail validation"

    def test_validate_nan_values(self):
        """Test validation rejects NaN values."""
        model = FingerprintModel()
        fp = np.zeros(9, dtype=np.float64)
        fp[4] = np.nan
        assert not model.validate_fingerprint(fp), "NaN values should fail validation"

    def test_validate_out_of_bounds(self):
        """Test validation rejects out-of-bounds values."""
        model = FingerprintModel()
        fp = np.ones(9, dtype=np.float64)  
        fp[6] = 3.0  # Tortuosity out of bounds [1.0, 2.5]
        assert not model.validate_fingerprint(fp), "Out-of-bounds should fail validation"


class TestScoreComputation:
    """Test outcome quality score computation."""

    def test_safety_score_bounds(self):
        """Test that safety score is guaranteed in [0, 1]."""
        model = FingerprintModel()
        
        # Low ESDF (far from obstacles)
        safe_low = model.compute_safety_score(0.0)
        assert 0.0 <= safe_low <= 1.0
        
        # Normal ESDF
        safe_mid = model.compute_safety_score(0.25)
        assert 0.0 <= safe_mid <= 1.0
        
        # High ESDF (very safe - should still be capped at 1.0)
        safe_high = model.compute_safety_score(10.0)
        assert safe_high == 1.0, "Safety score should be capped at 1.0"

    def test_smoothness_score_bounds(self):
        """Test that smoothness score is in [0, 1]."""
        model = FingerprintModel()
        
        smooth_low = model.compute_smoothness_score(1.0)
        assert smooth_low == 0.0, "High jerk should give 0 smoothness"
        
        smooth_high = model.compute_smoothness_score(0.0)
        assert smooth_high == 1.0, "Low jerk should give 1 smoothness"
        
        smooth_mid = model.compute_smoothness_score(0.5)
        assert 0.0 <= smooth_mid <= 1.0

    def test_outcome_quality_aggregation(self):
        """Test outcome quality aggregation."""
        model = FingerprintModel()
        
        # Perfect scores
        quality_perfect = model.compute_outcome_quality(1.0, 1.0, 1.0)
        assert quality_perfect == 1.0, "Perfect scores should give quality = 1.0"
        
        # Zero scores
        quality_zero = model.compute_outcome_quality(0.0, 0.0, 0.0)
        assert quality_zero == 0.0, "Zero scores should give quality = 0.0"
        
        # Weighted average: 0.4*0.8 + 0.35*0.6 + 0.25*0.4 = 0.32 + 0.21 + 0.1 = 0.63
        quality_mixed = model.compute_outcome_quality(0.8, 0.6, 0.4)
        expected = 0.4 * 0.8 + 0.35 * 0.6 + 0.25 * 0.4
        assert abs(quality_mixed - expected) < 1e-6


class TestSimilarity:
    """Test weighted cosine similarity."""

    def test_similarity_identical_vectors(self):
        """Test that identical vectors have similarity = 1."""
        model = FingerprintModel()
        fp = np.ones(9, dtype=np.float64) * 0.5
        fp[6] = 1.5  # Adjust tortuosity to valid range
        
        sim = model.weighted_cosine_similarity(fp, fp)
        assert abs(sim - 1.0) < 1e-6, "Identical vectors should have similarity = 1"

    def test_similarity_orthogonal_vectors(self):
        """Test that non-identical vectors can have lower similarity."""
        model = FingerprintModel()
        # Vector with mostly high values
        fp1 = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.5, 1.0, 1.0], dtype=np.float64)
        # Vector with mostly low values (but valid for f[6])
        fp2 = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)
        
        sim = model.weighted_cosine_similarity(fp1, fp2)
        # These vectors have very different magnitudes, similarity should be < 1
        assert sim < 1.0, "Different vectors should not have similarity = 1.0"

    def test_similarity_bounds(self):
        """Test that similarity is always in [0, 1]."""
        model = FingerprintModel()
        
        # Random fingerprints
        for _ in range(10):
            fp1 = np.random.rand(9)
            fp1[6] = 1.0 + np.random.rand() * 1.5  # Tortuosity [1, 2.5]
            fp2 = np.random.rand(9)
            fp2[6] = 1.0 + np.random.rand() * 1.5
            
            sim = model.weighted_cosine_similarity(fp1, fp2)
            assert 0.0 <= sim <= 1.0, f"Similarity {sim} out of [0, 1]"


class TestKNN:
    """Test k-NN retrieval."""

    def setup_method(self):
        """Setup test fixtures."""
        self.model = FingerprintModel(quality_threshold=0.5)
        
        # Add test episodes
        for i in range(5):
            spec = MissionSpec(
                start_x=float(i * 5),
                start_y=float(i * 5),
                end_x=float(i * 5 + 10),
                end_y=float(i * 5 + 10),
                estimated_distance=20.0 + i,
                obstacle_density=0.1 + i * 0.05,
            )
            fp = self.model.compute_fingerprint(spec)
            
            episode = EpisodeMetadata(
                episode_id=f"ep_test_{i:03d}",
                fingerprint=fp,
                original_params={"max_adv": 0.8},
                efficiency_score=0.8 + i * 0.05,
                safety_score=0.7 + i * 0.05,
                smoothness_score=0.6 + i * 0.05,
                outcome_quality=0.75,
                timestamp_ms=1000 + i,
            )
            self.model.add_episode(episode)

    def test_knn_returns_k(self):
        """Test that k-NN returns exactly k results."""
        spec = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=10.0,
            estimated_distance=20.0,
            obstacle_density=0.1,
        )
        
        result = self.model.query_knn(spec, k=3)
        assert len(result.top_k) == 3, f"Expected 3 results, got {len(result.top_k)}"
        assert len(result.similarities) == 3

    def test_knn_sorted_by_similarity(self):
        """Test that results are sorted by similarity descending."""
        spec = MissionSpec(
            start_x=0.0, start_y=0.0,
            end_x=10.0, end_y=10.0,
            estimated_distance=20.0,
            obstacle_density=0.1,
        )
        
        result = self.model.query_knn(spec, k=5)
        
        for i in range(len(result.similarities) - 1):
            assert result.similarities[i] >= result.similarities[i + 1], \
                "Results should be sorted by similarity descending"

    def test_knn_quality_filtering(self):
        """Test that low-quality episodes are filtered."""
        # Add low-quality episode
        spec = MissionSpec(
            start_x=-39.0, start_y=-39.0,
            end_x=-20.0, end_y=-20.0,
            estimated_distance=30.0,
            obstacle_density=0.9,
        )
        fp = self.model.compute_fingerprint(spec)
        
        low_quality = EpisodeMetadata(
            episode_id="ep_low_quality",
            fingerprint=fp,
            original_params={"max_adv": 0.8},
            efficiency_score=0.1,
            safety_score=0.1,
            smoothness_score=0.1,
            outcome_quality=0.1,  # Below threshold
            timestamp_ms=1000,
        )
        self.model.add_episode(low_quality)
        
        # Query should not return low-quality episode
        result = self.model.query_knn(spec, k=10)
        episode_ids = [ep.episode_id for ep in result.top_k]
        assert "ep_low_quality" not in episode_ids, "Low-quality episode should be filtered"


class TestPerturbation:
    """Test perturbation strategy."""

    def test_perturbation_tight(self):
        """Test tight exploitation strategy (sim > 0.95)."""
        model = FingerprintModel()
        pert = model.compute_perturbation(0.97)
        
        assert pert["sigma_pct"] == 0.03, "Tight sigma should be 3%"
        assert pert["strategy"] == "tight_exploitation"

    def test_perturbation_broad(self):
        """Test broad exploration strategy (sim < 0.80)."""
        model = FingerprintModel()
        pert = model.compute_perturbation(0.75)
        
        assert pert["sigma_pct"] == 0.10, "Broad sigma should be 10%"
        assert pert["strategy"] == "broad_exploration"

    def test_perturbation_linear(self):
        """Test linear interpolation strategy (0.80 <= sim <= 0.95)."""
        model = FingerprintModel()
        pert = model.compute_perturbation(0.875)
        
        # At 0.875, halfway between 0.80 and 0.95
        # σ = 0.03 + 0.07 * (0.875 - 0.80) / 0.15 = 0.03 + 0.07 * 0.5 = 0.065
        expected = 0.03 + 0.07 * (0.875 - 0.80) / 0.15
        assert abs(pert["sigma_pct"] - expected) < 1e-6, "Linear interpolation incorrect"
        assert pert["strategy"] == "linear_interpolation"


class TestPersistence:
    """Test JSON persistence."""

    def test_save_load_cycle(self, tmp_path):
        """Test saving and loading index."""
        model = FingerprintModel()
        
        # Add episodes
        for i in range(3):
            spec = MissionSpec(
                start_x=0.0, start_y=0.0,
                end_x=10.0, end_y=10.0,
                estimated_distance=20.0,
                obstacle_density=0.5,
            )
            fp = model.compute_fingerprint(spec)
            
            episode = EpisodeMetadata(
                episode_id=f"ep_save_{i}",
                fingerprint=fp,
                original_params={"max_adv": 0.8},
                efficiency_score=0.8,
                safety_score=0.7,
                smoothness_score=0.6,
                outcome_quality=0.75,
                timestamp_ms=1000 + i,
            )
            model.add_episode(episode)
        
        # Save
        filepath = tmp_path / "test_index.json"
        assert model.save_index(str(filepath)), "Save failed"
        assert filepath.exists(), "Index file not created"
        
        # Load into new model
        model2 = FingerprintModel()
        assert model2.load_index(str(filepath)), "Load failed"
        
        # Verify
        assert model2.get_episode_count() == 3, "Episode count mismatch"
        assert model2.index_.episodes[0].episode_id == "ep_save_0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
