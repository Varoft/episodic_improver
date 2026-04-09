#!/usr/bin/env python3
"""
recommendation_engine.py: Recommendation engine for parameter optimization.

Integrates:
- FingerprintModel for k-NN mission retrieval
- Parameter perturbation based on similarity
- Query processing and recommendation generation
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    # When imported as a package module
    from .episodic_improver import FingerprintModel, MissionSpec, EpisodeMetadata
    from .episodic_improver_7d import EpisodicImprover7D
except ImportError:
    # When run directly
    from episodic_improver import FingerprintModel, MissionSpec, EpisodeMetadata
    try:
        from episodic_improver_7d import EpisodicImprover7D
    except ImportError:
        EpisodicImprover7D = None


logger = logging.getLogger(__name__)


@dataclass
class ParameterRange:
    """Valid range for a parameter."""
    min_val: float
    max_val: float
    
    def clip(self, value: float) -> float:
        """Clip value to valid range."""
        return np.clip(value, self.min_val, self.max_val)
    
    def noisy_sample(self, nominal: float, sigma_pct: float) -> float:
        """
        Generate perturbed sample from nominal value.
        
        Args:
            nominal: Nominal parameter value.
            sigma_pct: Perturbation magnitude as percentage (e.g., 3% -> 0.03).
        
        Returns:
            Perturbed value clipped to valid range.
        """
        sigma = nominal * sigma_pct  # Convert percentage to absolute value
        perturbed = nominal + np.random.normal(0, sigma)
        return self.clip(perturbed)


@dataclass
class RecommendationEngineConfig:
    """Configuration for recommendation engine."""
    fingerprint_index_path: Optional[Path] = None  # Path to load existing index
    outcome_quality_threshold: float = 0.70  # Min quality to include
    k_neighbors: int = 3  # Number of neighbors to retrieve
    
    # Parameter ranges for navigation controller
    param_ranges: Dict[str, ParameterRange] = None
    
    def __post_init__(self):
        """Initialize default parameter ranges if not provided."""
        if self.param_ranges is None:
            self.param_ranges = {
                # Example parameter ranges for a navigation controller
                "goal_tolerance": ParameterRange(0.05, 0.50),
                "max_velocity": ParameterRange(0.1, 2.0),
                "max_angular_velocity": ParameterRange(0.2, 3.0),
                "acceleration": ParameterRange(0.1, 1.0),
                "angular_acceleration": ParameterRange(0.1, 1.0),
            }


class RecommendationEngine:
    """
    Generates parameter recommendations based on similar past missions.
    
    Process:
    1. Parse query (mission specification + requested parameters)
    2. Compute mission fingerprint
    3. Query k-NN similar episodes
    4. Extract parameter sets from similar missions
    5. Apply adaptive perturbation based on similarity
    6. Return recommended parameter sets
    """
    
    def __init__(self, config: RecommendationEngineConfig):
        """
        Initialize recommendation engine.
        
        Args:
            config: RecommendationEngineConfig with model and param settings.
        """
        self.config = config
        self.model = FingerprintModel(
            quality_threshold=config.outcome_quality_threshold
        )
        self.improver_7d = None  # Optional 7D system for new pipeline
        
        # Load existing index if path provided
        if config.fingerprint_index_path:
            if self.model.load_index(str(config.fingerprint_index_path)):
                logger.info(
                    f"Loaded fingerprint index: {self.model.get_episode_count()} episodes"
                )
            else:
                logger.warning(
                    f"Failed to load index from {config.fingerprint_index_path}"
                )
    
    def enable_7d_system(self, index_7d_path: Optional[Path] = None) -> bool:
        """
        Enable the 7D episodic improver system for recommendations.
        
        Args:
            index_7d_path: Path to 7D index JSON file.
        
        Returns:
            True if 7D system initialized successfully, False otherwise.
        """
        if EpisodicImprover7D is None:
            logger.warning("EpisodicImprover7D not available, 7D system disabled")
            return False
        
        try:
            if index_7d_path and Path(index_7d_path).exists():
                self.improver_7d = EpisodicImprover7D(
                    index_path=str(index_7d_path),
                    learning_log_path="./episodic_memory/learning_log.json"
                )
                logger.info(f"✓ 7D system enabled with index: {index_7d_path}")
                return True
            else:
                logger.warning(f"7D index path not found or not provided: {index_7d_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize 7D system: {e}")
            return False
    
    def add_episode(
        self,
        episode_id: str,
        mission_spec: MissionSpec,
        params: Dict[str, float],
        efficiency: float,
        safety: float,
        smoothness: float,
    ) -> bool:
        """
        Add episode to the fingerprint index.
        
        Args:
            episode_id: Unique episode identifier.
            mission_spec: MissionSpec for this episode.
            params: Parameter dictionary from the robot.
            efficiency: Path efficiency score [0, 1].
            safety: Safety score [0, 1].
            smoothness: Smoothness score [0, 1].
        
        Returns:
            True if added successfully, False otherwise.
        """
        try:
            # Compute fingerprint
            fingerprint = self.model.compute_fingerprint(mission_spec)
            
            # Compute outcome quality
            outcome_quality = self.model.compute_outcome_quality(
                efficiency, safety, smoothness
            )
            
            # Create metadata object
            metadata = EpisodeMetadata(
                episode_id=episode_id,
                fingerprint=fingerprint,
                original_params=params,
                efficiency_score=efficiency,
                safety_score=safety,
                smoothness_score=smoothness,
                outcome_quality=outcome_quality,
                timestamp_ms=int(time.time() * 1000),
            )
            
            # Add to model
            self.model.add_episode(metadata)
            logger.info(f"Added episode: {episode_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add episode {episode_id}: {e}")
            return False
    
    def generate_recommendations(
        self,
        query_id: str,
        mission_spec: MissionSpec,
    ) -> Dict:
        """
        Generate parameter recommendations for a mission.
        
        Args:
            query_id: Query identifier (for tracing).
            mission_spec: MissionSpec describing the target mission.
        
        Returns:
            Dictionary with:
            - query_id: Query ID
            - recommendations: List[Dict] of parameter sets with metadata
            - statistics: Query statistics
        """
        try:
            # Query k-NN similar episodes
            result = self.model.query_knn(mission_spec, k=self.config.k_neighbors)
            
            if not result.top_k:
                logger.warning(f"Query {query_id}: No similar episodes found")
                return {
                    "query_id": query_id,
                    "mission_spec": mission_spec.to_dict(),
                    "recommendations": [],
                    "status": "no_similar_episodes",
                    "statistics": {
                        "episodes_examined": result.episodes_considered,
                        "episodes_filtered": result.episodes_filtered,
                        "mean_similarity": result.mean_similarity,
                    }
                }
            
            # Compute perturbation strategy based on similarity
            perturbation_info = self.model.compute_perturbation(result.mean_similarity)
            sigma_pct = perturbation_info['sigma_pct']  # Already as fraction (0.03, 0.10, etc)
            
            # Generate recommendations from similar episodes
            recommendations = []
            for idx, (episode, similarity) in enumerate(zip(result.top_k, result.similarities)):
                # Extract original parameters
                nominal_params = episode.original_params.copy()
                
                # Apply adaptive perturbation to each parameter
                perturbed_params = {}
                for param_name, param_range in self.config.param_ranges.items():
                    if param_name in nominal_params:
                        perturbed_val = param_range.noisy_sample(
                            nominal_params[param_name],
                            sigma_pct
                        )
                        perturbed_params[param_name] = float(perturbed_val)
                
                # Recommendation entry
                recommendation = {
                    "rank": idx + 1,
                    "source_episode_id": episode.episode_id,
                    "similarity": float(similarity),
                    "source_quality_scores": {
                        "efficiency": float(episode.efficiency_score),
                        "safety": float(episode.safety_score),
                        "smoothness": float(episode.smoothness_score),
                        "outcome_quality": float(episode.outcome_quality),
                    },
                    "nominal_parameters": nominal_params,
                    "perturbation_info": {
                        "strategy": perturbation_info['strategy'],
                        "sigma_pct": float(perturbation_info['sigma_pct']) * 100.0,  # Convert to percentage
                    },
                    "recommended_parameters": perturbed_params,
                }
                recommendations.append(recommendation)
            
            # Return full recommendation
            return {
                "query_id": query_id,
                "mission_spec": mission_spec.to_dict(),
                "query_fingerprint": self.model.compute_fingerprint(mission_spec).tolist(),
                "recommendations": recommendations,
                "status": "success",
                "statistics": {
                    "mean_similarity": float(result.mean_similarity),
                    "episodes_examined": result.episodes_considered,
                    "episodes_filtered": result.episodes_filtered,
                    "recommendations_returned": len(recommendations),
                }
            }
        
        except Exception as e:
            logger.error(f"Error generating recommendations for {query_id}: {e}")
            return {
                "query_id": query_id,
                "mission_spec": mission_spec.to_dict(),
                "recommendations": [],
                "status": f"error: {str(e)}",
                "statistics": {}
            }
    
    def generate_recommendations_7d(
        self,
        query_id: str,
        mission_spec: MissionSpec,
    ) -> Dict:
        """
        Generate parameter recommendations using the 7D system (PRE-MISIÓN).
        
        Uses EpisodicImprover7D for advanced fingerprint extraction and
        adaptive perturbation based on similarity scaling.
        
        Args:
            query_id: Query identifier for tracing.
            mission_spec: MissionSpec describing the target mission.
        
        Returns:
            Dictionary with 7D recommendations or error status.
        """
        if self.improver_7d is None:
            logger.warning(f"7D system not initialized for query {query_id}. Falling back to standard engine.")
            return self.generate_recommendations(query_id, mission_spec)
        
        try:
            logger.info(f"Generating 7D recommendations for query {query_id}")
            
            # Use 7D system for PRE-MISIÓN prediction
            prediction = self.improver_7d.pre_mission_prediction(
                src_x=mission_spec.start_x,
                src_y=mission_spec.start_y,
                target_x=mission_spec.end_x,
                target_y=mission_spec.end_y,
                obstacle_density=mission_spec.obstacle_density,
                estimated_distance=mission_spec.estimated_distance
            )
            
            if prediction['status'] != 'ready':
                return {
                    "query_id": query_id,
                    "system": "7d",
                    "mission_spec": mission_spec.to_dict(),
                    "recommendations": [],
                    "status": f"7d_prediction_failed: {prediction.get('error', 'unknown')}",
                    "statistics": {}
                }
            
            # Extract prediction results
            best_match_id = prediction['best_match_id']
            similarity = prediction['best_match_similarity']
            predicted_params = prediction['predicted_params']
            search_results = prediction['search_results']
            
            # Build recommendation entries from 7D search results
            recommendations = []
            for result in search_results:
                recommendation = {
                    "rank": result['rank'],
                    "source_episode_id": result['episode_id'],
                    "similarity": float(result['similarity_score']),
                    "source_quality_scores": {
                        "composite_score": result.get('composite_score', None),
                    },
                    "nominal_parameters": {},  # Not available in 7D system
                    "perturbation_info": {
                        "strategy": "7d_adaptive_sigma",
                        "sigma_pct": None,  # Handled by 7D system internally
                    },
                    "recommended_parameters": predicted_params if result['rank'] == 1 else None,
                }
                recommendations.append(recommendation)
            
            return {
                "query_id": query_id,
                "system": "7d",
                "mission_spec": mission_spec.to_dict(),
                "fingerprint_7d": prediction['fingerprint_7d'],
                "recommendations": recommendations,
                "best_match_id": best_match_id,
                "best_match_similarity": similarity,
                "predicted_parameters": predicted_params,
                "perturbation_details": prediction.get('perturbation', {}),
                "status": "success",
                "statistics": {
                    "mean_similarity": similarity,
                    "search_depth": len(search_results),
                    "best_match_found": True,
                }
            }
        
        except Exception as e:
            logger.error(f"Error in 7D recommendation generation for {query_id}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "query_id": query_id,
                "system": "7d",
                "mission_spec": mission_spec.to_dict(),
                "recommendations": [],
                "status": f"error: {str(e)}",
                "statistics": {}
            }
    
    def post_mission_evaluation_7d(self, mission_outcome: Dict) -> Dict:
        """
        Evaluate mission outcome using 7D system (POST-MISIÓN).
        
        Registers improvements/failures in the learning log and updates statistics.
        
        Args:
            mission_outcome: Result from SLAMO including composite_score.
        
        Returns:
            Dictionary with evaluation results.
        """
        if self.improver_7d is None:
            logger.warning("7D system not available for post-mission evaluation")
            return {
                "status": "error",
                "error": "7D system not initialized",
            }
        
        try:
            evaluation = self.improver_7d.post_mission_evaluation(mission_outcome)
            logger.info(
                f"Mission outcome evaluated: "
                f"improvement={evaluation.get('is_improvement', False)}, "
                f"delta={evaluation.get('improvement_delta', 0):.2f}"
            )
            return evaluation
        
        except Exception as e:
            logger.error(f"Error in post-mission evaluation: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    def save_index(self, filepath: str) -> bool:
        """
        Save fingerprint index to disk.
        
        Args:
            filepath: Path to save index.
        
        Returns:
            True if successful.
        """
        return self.model.save_index(filepath)
    
    def load_index(self, filepath: str) -> bool:
        """
        Load fingerprint index from disk.
        
        Args:
            filepath: Path to load index from.
        
        Returns:
            True if successful.
        """
        return self.model.load_index(filepath)
    
    def get_episode_count(self) -> int:
        """Get number of episodes in index."""
        return self.model.get_episode_count()


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create engine
    config = RecommendationEngineConfig(
        outcome_quality_threshold=0.70,
        k_neighbors=3,
    )
    engine = RecommendationEngine(config)
    
    # Add sample episodes
    print("Adding sample episodes...")
    
    # Episode 1: Baseline mission
    mission1 = MissionSpec(
        start_x=0.0, start_y=-27.0,
        end_x=0.0, end_y=26.8,
        estimated_distance=54.0,
        obstacle_density=0.12
    )
    params1 = {
        "goal_tolerance": 0.10,
        "max_velocity": 1.0,
        "max_angular_velocity": 1.5,
        "acceleration": 0.5,
        "angular_acceleration": 0.3,
    }
    engine.add_episode(
        episode_id="ep_001",
        mission_spec=mission1,
        params=params1,
        efficiency=0.90,
        safety=0.80,
        smoothness=0.85,
    )
    
    # Episode 2: Similar mission with different params
    mission2 = MissionSpec(
        start_x=0.1, start_y=-26.9,
        end_x=0.1, end_y=26.9,
        estimated_distance=54.2,
        obstacle_density=0.13
    )
    params2 = {
        "goal_tolerance": 0.12,
        "max_velocity": 0.95,
        "max_angular_velocity": 1.4,
        "acceleration": 0.48,
        "angular_acceleration": 0.32,
    }
    engine.add_episode(
        episode_id="ep_002",
        mission_spec=mission2,
        params=params2,
        efficiency=0.88,
        safety=0.82,
        smoothness=0.83,
    )
    
    # Query for recommendations
    print("\nGenerating recommendations...")
    query_mission = MissionSpec(
        start_x=0.0, start_y=-27.0,
        end_x=0.0, end_y=26.8,
        estimated_distance=54.0,
        obstacle_density=0.11
    )
    
    recommendations = engine.generate_recommendations(
        query_id="query_001",
        mission_spec=query_mission
    )
    
    # Display results
    print("\n" + "="*70)
    print("RECOMMENDATION RESULT")
    print("="*70)
    print(json.dumps(recommendations, indent=2))
    
    # Get episode count
    print(f"\nTotal episodes in index: {engine.get_episode_count()}")
