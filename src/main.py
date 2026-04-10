#!/usr/bin/env python3
"""
main.py: Main entry point for episodic improver component.

Orchestrates:
1. Loads/initializes fingerprint index
2. Monitors episodic_memory/ for new episodes
3. Monitors etc/ for new queries
4. Generates recommendations and saves results
"""

import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

try:
    # When imported as a package module
    from .directory_monitor import DirectoryMonitor, MonitorConfig
    from .recommendation_engine import RecommendationEngine, RecommendationEngineConfig
    from .episodic_improver import MissionSpec
    from .config_manager import ConfigManager
except ImportError:
    # When run directly
    from directory_monitor import DirectoryMonitor, MonitorConfig
    from recommendation_engine import RecommendationEngine, RecommendationEngineConfig
    from episodic_improver import MissionSpec
    from config_manager import ConfigManager


logger = logging.getLogger(__name__)


class EpisodicImproverComponent:
    """
    Main component integrating directory monitoring and recommendations.
    """
    
    # Default configuration paths
    DEFAULT_EPISODIC_MEMORY_DIR = Path("episodic_memory")
    DEFAULT_ETC_DIR = Path("etc")
    DEFAULT_CONFIG_FILE = DEFAULT_ETC_DIR / "config.toml"
    DEFAULT_INDEX_FILE = DEFAULT_ETC_DIR / "fingerprint_index.json"
    DEFAULT_RECOMMENDATIONS_DIR = DEFAULT_ETC_DIR / "recommendations"
    
    def __init__(
        self,
        episodic_memory_dir: Optional[Path] = None,
        etc_dir: Optional[Path] = None,
        index_file: Optional[Path] = None,
        config_file: Optional[Path] = None,
    ):
        """
        Initialize component.
        
        Args:
            episodic_memory_dir: Base directory for episodic memory episodes.
            etc_dir: Configuration directory.
            index_file: Path to fingerprint index JSON.
            config_file: Path to configuration TOML file (optional).
        """
        # Load configuration
        config_mgr = ConfigManager(config_file)
        config_mgr.load()
        config = config_mgr.get()
        
        # Set directories (CLI args override config file)
        self.episodic_memory_dir = (
            episodic_memory_dir or 
            Path(config.directories.episodic_memory_dir) or 
            self.DEFAULT_EPISODIC_MEMORY_DIR
        )
        self.etc_dir = (
            etc_dir or 
            Path(config.directories.query_dir) or 
            self.DEFAULT_ETC_DIR
        )
        self.index_file = (
            index_file or 
            Path(config.directories.index_file) or 
            self.DEFAULT_INDEX_FILE
        )
        # Recommendations dir is always under etc_dir
        self.recommendations_dir = self.etc_dir / "recommendations"
        
        # Store config for later use
        self.config = config
        
        # Create directories
        self.episodic_memory_dir.mkdir(parents=True, exist_ok=True)
        self.etc_dir.mkdir(parents=True, exist_ok=True)
        self.recommendations_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize recommendation engine
        engine_config = RecommendationEngineConfig(
            fingerprint_index_path=self.index_file if self.index_file.exists() else None,
            outcome_quality_threshold=config.fingerprint.outcome_quality_threshold,
            k_neighbors=config.fingerprint.k_neighbors,
        )
        self.engine = RecommendationEngine(engine_config)
        
        # Try to enable 7D episodic improver system
        index_7d_path = self.episodic_memory_dir / "fingerprints_index_unified_7d.json"
        if index_7d_path.exists():
            if self.engine.enable_7d_system(index_7d_path):
                self.use_7d_system = True
                logger.info(f"✓ 7D system enabled with index: {index_7d_path}")
            else:
                self.use_7d_system = False
                logger.warning("7D system failed to initialize, using standard engine")
        else:
            self.use_7d_system = False
            logger.info(f"7D index not found at {index_7d_path}, using standard engine")
        
        logger.info(
            f"EpisodicImproverComponent initialized:\n"
            f"  episodic_memory: {self.episodic_memory_dir}\n"
            f"  etc: {self.etc_dir}\n"
            f"  index: {self.index_file}\n"
            f"  episodes in index: {self.engine.get_episode_count()}\n"
            f"  7D system: {'ENABLED' if self.use_7d_system else 'DISABLED'}\n"
            f"  config: outcome_quality_threshold={config.fingerprint.outcome_quality_threshold}, "
            f"k_neighbors={config.fingerprint.k_neighbors}"
        )
        
        # Initialize directory monitor
        monitor_config = MonitorConfig(
            episodic_memory_dir=self.episodic_memory_dir,
            query_dir=self.etc_dir,
            recommendations_dir=self.recommendations_dir,
            ttl_seconds=config.monitoring.ttl_seconds,
            cleanup_interval_seconds=config.monitoring.cleanup_interval_seconds,
        )
        self.monitor = DirectoryMonitor(monitor_config)
        self.monitor.register_episode_callback(self._on_episode_detected)
        self.monitor.register_query_callback(self._on_query_detected)
        self.monitor.register_mission_callback(self._on_mission_initial_detected)
        
        logger.info("Component initialized successfully")
    
    def _on_episode_detected(self, episode_path: Path) -> None:
        """
        Callback when new episode is detected.
        
        Args:
            episode_path: Path to episode JSON file.
        """
        logger.info(f"Processing episode: {episode_path.name}")
        
        try:
            # Load episode data
            episode_data = self.monitor.load_episode(episode_path)
            if not episode_data:
                return
            
            # Extract mission spec
            mission_data = episode_data.get("mission_spec", {})
            mission_spec = MissionSpec(
                start_x=mission_data.get("start_x", 0.0),
                start_y=mission_data.get("start_y", 0.0),
                end_x=mission_data.get("end_x", 0.0),
                end_y=mission_data.get("end_y", 0.0),
                estimated_distance=mission_data.get("estimated_distance", 0.0),
                obstacle_density=mission_data.get("obstacle_density", 0.0),
            )
            
            # Extract scores
            scores = episode_data.get("scores", {})
            efficiency = scores.get("efficiency", 0.5)
            safety = scores.get("safety", 0.5)
            smoothness = scores.get("smoothness", 0.5)
            
            # Extract parameters
            params = episode_data.get("parameters", {})
            
            # Add to engine
            self.engine.add_episode(
                episode_id=episode_path.stem,  # Remove .json extension
                mission_spec=mission_spec,
                params=params,
                efficiency=efficiency,
                safety=safety,
                smoothness=smoothness,
            )
            
            logger.info(f"✓ Episode {episode_path.name} added to index")
        
        except Exception as e:
            logger.error(f"✗ Failed to process episode {episode_path.name}: {e}")
    
    def _on_query_detected(self, query_path: Path) -> None:
        """
        Callback when new query is detected.
        
        Args:
            query_path: Path to query_pending.json file.
        """
        logger.info(f"Processing query: {query_path.name}")
        
        try:
            # Load query data
            query_data = self.monitor.load_query_pending(query_path)
            if not query_data:
                return
            
            query_id = query_data.get("query_id", "unknown")
            mission_data = query_data.get("mission_spec", {})
            
            # Create mission spec
            mission_spec = MissionSpec(
                start_x=mission_data.get("start_x", 0.0),
                start_y=mission_data.get("start_y", 0.0),
                end_x=mission_data.get("end_x", 0.0),
                end_y=mission_data.get("end_y", 0.0),
                estimated_distance=mission_data.get("estimated_distance", 0.0),
                obstacle_density=mission_data.get("obstacle_density", 0.0),
            )
            
            # Generate recommendations using 7D system if available, otherwise fall back
            logger.info(f"Generating recommendations for query {query_id}... (using {'7D' if self.use_7d_system else 'standard'} engine)")
            if self.use_7d_system:
                recommendations = self.engine.generate_recommendations_7d(
                    query_id=query_id,
                    mission_spec=mission_spec
                )
            else:
                recommendations = self.engine.generate_recommendations(
                    query_id=query_id,
                    mission_spec=mission_spec
                )
            
            # Save recommendations
            self.monitor.save_recommendation(
                query_id=query_id,
                recommendation_data=recommendations,
                output_dir=self.recommendations_dir
            )
            
            logger.info(
                f"✓ Query {query_id} processed. "
                f"Generated {len(recommendations.get('recommendations', []))} recommendations"
            )
            
            # Remove processed query
            try:
                query_path.unlink()
                logger.info(f"Removed processed query file: {query_path.name}")
            except OSError as e:
                logger.warning(f"Could not remove query file {query_path.name}: {e}")
        
        except Exception as e:
            logger.error(f"✗ Failed to process query {query_path.name}: {e}")
    
    def _on_mission_initial_detected(self, mission_path: Path) -> None:
        """
        Callback when mission_initial*.json is detected (PRE-MISIÓN).
        
        [PHASE 1] Detects mission start event and generates 7D parameter predictions.
        - Extracts mission specification (geometry, obstacles)
        - Uses 7D fingerprinting to find similar historical missions
        - Generates predicted control parameters based on best match
        - Saves predictions for SLAMO to consume
        
        Args:
            mission_path: Path to mission_initial*.json file.
        """
        logger.info(f"→ [PRE-MISIÓN] Mission initial file detected: {mission_path.name}")
        
        try:
            # Load mission initial data
            with open(mission_path, 'r') as f:
                mission_data = json.load(f)
            
            mission_id = mission_data.get("mission_id", f"mission_{int(time.time() * 1000)}")
            
            # Extract mission spec for 7D fingerprinting
            mission_spec = MissionSpec(
                start_x=mission_data.get("start_x", 0.0),
                start_y=mission_data.get("start_y", 0.0),
                end_x=mission_data.get("end_x", 0.0),
                end_y=mission_data.get("end_y", 0.0),
                estimated_distance=mission_data.get("estimated_distance", 0.0),
                obstacle_density=mission_data.get("obstacle_density", 0.0),
            )
            
            logger.info(
                f"  Mission spec: ({mission_spec.start_x:.1f}, {mission_spec.start_y:.1f}) "
                f"→ ({mission_spec.end_x:.1f}, {mission_spec.end_y:.1f}), "
                f"obstacle_density={mission_spec.obstacle_density:.2f}"
            )
            
            # [PRE-MISIÓN] Generate 7D predictions
            if not self.use_7d_system:
                logger.warning("⚠ 7D system not available, using default parameters")
                return
            
            logger.info(f"  Generating 7D predictions...")
            prediction = self.engine.generate_recommendations_7d(
                query_id=mission_id,
                mission_spec=mission_spec
            )
            
            if prediction.get('status') not in ['ready', 'success']:
                logger.warning(
                    f"✗ 7D prediction failed: {prediction.get('status')}"
                )
                return
            
            # Extract prediction details from 7D engine response
            best_match_id = prediction.get('best_match_id', 'unknown')
            best_match_similarity = prediction.get('best_match_similarity', 0.0)
            predicted_params = prediction.get('predicted_parameters', {})
            fingerprint_7d = prediction.get('fingerprint_7d', [])
            search_results = prediction.get('search_results', [])
            
            # Create output predictions document (PROTOCOL)
            predictions_output = {
                "mission_id": mission_id,
                "timestamp_ms": int(time.time() * 1000),
                "status": "ready",
                "fingerprint_7d": fingerprint_7d,
                "best_match_id": best_match_id,
                "best_match_similarity": best_match_similarity,
                "predicted_parameters": predicted_params,
                "search_results": search_results,
                "perturbation": prediction.get('perturbation_details', {}),
            }
            
            # Save predictions file for SLAMO to consume
            predictions_file = self.episodic_memory_dir / f"predictions_{mission_id}.json"
            with open(predictions_file, 'w') as f:
                json.dump(predictions_output, f, indent=2)
            
            logger.info(
                f"✓ [PRE-MISIÓN] Predictions generated and saved:\n"
                f"    Best match: {best_match_id}\n"
                f"    Similarity: {best_match_similarity:.1%}\n"
                f"    Predicted params: {len(predicted_params)} parameters\n"
                f"    Output file: {predictions_file.name}"
            )
        
        except json.JSONDecodeError as e:
            logger.error(f"✗ Invalid JSON in mission file {mission_path.name}: {e}")
        except Exception as e:
            logger.error(f"✗ Failed to process mission initial {mission_path.name}: {e}")
            import traceback
            traceback.print_exc()
    
    def save_episode(self, mission_data: dict) -> bool:
        """
        Save completed mission as episode in episodic memory.
        
        Called after SLAMO completes a mission. Takes mission_initial.json data
        (now with results) and saves as episode for future reference.
        
        Args:
            mission_data: Complete mission data dict including:
                - mission_id: str
                - start_x, start_y, end_x, end_y: float
                - obstacle_density, estimated_distance: float
                - control_params: dict with parameters used
                - success: bool
                - time_to_goal_s: float
                - collisions: int
                - composite_score: float
                - etc.
        
        Returns:
            True if saved successfully, False otherwise.
        """
        try:
            mission_id = mission_data.get('mission_id', f'ep_{int(time.time() * 1000)}')
            
            # Create episode data structure
            episode = {
                'mission_id': mission_id,
                'timestamp_ms': int(time.time() * 1000),
                'mission_spec': {
                    'start_x': mission_data.get('start_x'),
                    'start_y': mission_data.get('start_y'),
                    'end_x': mission_data.get('end_x'),
                    'end_y': mission_data.get('end_y'),
                    'estimated_distance': mission_data.get('estimated_distance'),
                    'obstacle_density': mission_data.get('obstacle_density'),
                },
                'control_params': mission_data.get('control_params', {}),
                'predicted_from_episode': mission_data.get('predicted_from_episode'),
                'similarity_score': mission_data.get('similarity_score'),
                'mission_outcome': {
                    'success': mission_data.get('success'),
                    'time_to_goal_s': mission_data.get('time_to_goal_s'),
                    'collisions': mission_data.get('collisions', 0),
                    'blocked_time_s': mission_data.get('blocked_time_s', 0),
                    'composite_score': mission_data.get('composite_score'),
                },
            }
            
            # Save episode
            episode_path = self.episodic_memory_dir / f"{mission_id}.json"
            with open(episode_path, 'w') as f:
                json.dump(episode, f, indent=2)
            
            logger.info(f"✓ Episode saved: {episode_path.name}")
            return True
        
        except Exception as e:
            logger.error(f"✗ Failed to save episode: {e}")
            return False
    
    def start(self) -> None:
        """Start the component."""
        logger.info("Starting EpisodicImproverComponent...")
        self.monitor.start()
        logger.info("Component started and monitoring directories")
    
    def stop(self) -> None:
        """Stop the component and save index."""
        logger.info("Stopping EpisodicImproverComponent...")
        
        # Save index before stopping
        if self.engine.get_episode_count() > 0:
            if self.engine.save_index(str(self.index_file)):
                logger.info(
                    f"Saved index with {self.engine.get_episode_count()} episodes "
                    f"to {self.index_file}"
                )
            else:
                logger.error("Failed to save index")
        
        self.monitor.stop()
        logger.info("Component stopped")
    
    def run_forever(self) -> None:
        """
        Start component and run forever (or until interrupted).
        
        Sets up signal handlers for graceful shutdown.
        """
        def signal_handler(sig, frame):
            logger.info("Received SIGINT, shutting down...")
            self.stop()
            sys.exit(0)
        
        # Register signal handler
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start component
        self.start()
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run component
    component = EpisodicImproverComponent()
    component.run_forever()


if __name__ == "__main__":
    main()
