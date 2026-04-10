#!/usr/bin/env python3
"""
slamo_bridge.py: Public API for SLAMO to consume episodic improver predictions.

This module provides a file-based interface for SLAMO to:
1. Write mission_initial_{mission_id}.json when a mission starts
2. Read predictions_{mission_id}.json for pre-mission parameter predictions
3. Write completed mission data for episodic memory storage

Design:
- Agnóstic to communication protocol (file-based, no Ice required)
- Can be imported as a Python module OR used as a standalone script
- Works with RoboComp SLAMO component seamlessly
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class MissionInitial:
    """Pre-mission specification written by SLAMO."""
    mission_id: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    estimated_distance: float
    obstacle_density: float
    timestamp_ms: int = None

    def __post_init__(self):
        if self.timestamp_ms is None:
            self.timestamp_ms = int(time.time() * 1000)

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "mission_id": self.mission_id,
            "timestamp_ms": self.timestamp_ms,
            "start_x": self.start_x,
            "start_y": self.start_y,
            "end_x": self.end_x,
            "end_y": self.end_y,
            "estimated_distance": self.estimated_distance,
            "obstacle_density": self.obstacle_density,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MissionInitial":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PredictionResult:
    """Pre-mission predictions returned by episodic improver."""
    mission_id: str
    status: str  # 'ready', 'error', 'timeout'
    best_match_id: str
    best_match_similarity: float
    predicted_parameters: Dict[str, float]  # Key: param name, Value: recommended value
    fingerprint_7d: list  # 7-dimensional fingerprint
    search_results: list  # Top-k results
    perturbation: dict  # Perturbation info
    timestamp_ms: int = None

    def __post_init__(self):
        if self.timestamp_ms is None:
            self.timestamp_ms = int(time.time() * 1000)

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "mission_id": self.mission_id,
            "timestamp_ms": self.timestamp_ms,
            "status": self.status,
            "best_match_id": self.best_match_id,
            "best_match_similarity": self.best_match_similarity,
            "predicted_parameters": self.predicted_parameters,
            "fingerprint_7d": self.fingerprint_7d,
            "search_results": self.search_results,
            "perturbation": self.perturbation,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PredictionResult":
        """Create from dictionary."""
        return cls(**data)


class SLAMOBridge:
    """
    File-based bridge between SLAMO and episodic improver.

    Usage in SLAMO (C++):
    ```cpp
    // At initialization
    auto bridge = std::make_unique<SLAMOBridge>("episodic_memory");

    // When user clicks destination (gotoPoint)
    auto predictions = bridge.get_predictions(
        robot_x, robot_y, target_x, target_y,
        obstacle_density, estimated_distance, mission_id
    );
    if (predictions.status == "ready") {
        trajectory_controller_.set_parameters(predictions.predicted_parameters);
    }

    // When mission completes
    bridge.save_mission_outcome(
        mission_id, success, time_to_goal, collisions, composite_score
    );
    ```

    Usage in Python:
    ```python
    bridge = SLAMOBridge("episodic_memory")

    # (1) Write mission initial
    mission = MissionInitial(
        mission_id="m123",
        start_x=10, start_y=15,
        end_x=50, end_y=45,
        estimated_distance=55, obstacle_density=0.45
    )
    bridge.write_mission_initial(mission)

    # (2) Wait for predictions
    predictions = bridge.wait_predictions("m123", timeout_s=5)
    print(f"Best match: {predictions.best_match_id}")
    print(f"Params: {predictions.predicted_parameters}")

    # (3) Record outcome
    bridge.save_mission_outcome(
        mission_id="m123",
        success=True,
        time_to_goal_s=42.5,
        collisions=0,
        composite_score=87.3
    )
    ```
    """

    def __init__(self, episodic_memory_dir: str = "episodic_memory"):
        """
        Initialize bridge.

        Args:
            episodic_memory_dir: Base directory where mission_initial_*.json
                                 and predictions_*.json files are exchanged.
        """
        self.episodic_memory_dir = Path(episodic_memory_dir)
        self.episodic_memory_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"SLAMOBridge initialized with directory: {self.episodic_memory_dir}")

    def write_mission_initial(self, mission: MissionInitial) -> bool:
        """
        Write mission_initial_{mission_id}.json for episodic improver to process.

        This is typically called by SLAMO when a gotoPoint is initiated.

        Args:
            mission: MissionInitial object with mission specification.

        Returns:
            True if successfully written, False otherwise.
        """
        try:
            mission_file = self.episodic_memory_dir / f"mission_initial_{mission.mission_id}.json"
            with open(mission_file, 'w') as f:
                json.dump(mission.to_dict(), f, indent=2)
            logger.info(f"✓ Written mission_initial: {mission_file.name}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to write mission_initial: {e}")
            return False

    def wait_predictions(
        self,
        mission_id: str,
        timeout_s: float = 5.0,
        poll_interval_s: float = 0.1
    ) -> Optional[PredictionResult]:
        """
        Wait for episodic improver to generate predictions.

        This is a blocking call that polls for predictions_{mission_id}.json
        until it appears or timeout occurs.

        Args:
            mission_id: Mission ID to wait for.
            timeout_s: Maximum time to wait in seconds.
            poll_interval_s: Time between polls in seconds.

        Returns:
            PredictionResult if predictions received, None if timeout.
        """
        predictions_file = self.episodic_memory_dir / f"predictions_{mission_id}.json"
        start_time = time.time()

        while time.time() - start_time < timeout_s:
            if predictions_file.exists():
                try:
                    with open(predictions_file, 'r') as f:
                        prediction_data = json.load(f)
                    logger.info(f"✓ Received predictions for {mission_id}")
                    return PredictionResult.from_dict(prediction_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in predictions file: {e}")
                    time.sleep(poll_interval_s)
                    continue

            time.sleep(poll_interval_s)

        logger.warning(f"✗ Timeout waiting for predictions ({mission_id})")
        return None

    def get_predictions(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        obstacle_density: float,
        estimated_distance: float,
        mission_id: str,
        timeout_s: float = 5.0
    ) -> Optional[PredictionResult]:
        """
        Convenience method: write mission_initial and wait for predictions.

        This is the typical flow for SLAMO:
        ```cpp
        auto pred = bridge.get_predictions(
            robot_x, robot_y, target_x, target_y,
            obs_density, est_distance, "m123"
        );
        if (pred && pred.status == "ready") {
            use_predicted_params(pred.predicted_parameters);
        }
        ```

        Args:
            start_x, start_y: Robot position.
            end_x, end_y: Target position.
            obstacle_density: [0, 1] obstacle density at start.
            estimated_distance: Estimated path distance in meters.
            mission_id: Unique mission identifier.
            timeout_s: Max time to wait for predictions.

        Returns:
            PredictionResult if successful, None if error or timeout.
        """
        # (1) Write mission_initial
        mission = MissionInitial(
            mission_id=mission_id,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            estimated_distance=estimated_distance,
            obstacle_density=obstacle_density,
        )
        if not self.write_mission_initial(mission):
            return None

        # (2) Wait for predictions
        return self.wait_predictions(mission_id, timeout_s=timeout_s)

    def save_mission_outcome(
        self,
        mission_id: str,
        success: bool,
        time_to_goal_s: float,
        collisions: int = 0,
        blocked_time_s: float = 0.0,
        composite_score: float = 0.0,
        predicted_from_episode: Optional[str] = None,
        similarity_score: Optional[float] = None,
        control_params: Optional[Dict] = None,
    ) -> bool:
        """
        Save mission outcome for episodic memory (POST-MISIÓN).

        Called by SLAMO after mission completes to record results
        in episodic memory for future learning.

        Args:
            mission_id: Mission identifier.
            success: Whether mission succeeded.
            time_to_goal_s: Time to reach goal in seconds.
            collisions: Number of collisions.
            blocked_time_s: Time spent blocked in seconds.
            composite_score: Overall mission quality score [0, 100].
            predicted_from_episode: Episode ID if predictions were used.
            similarity_score: Similarity to best match if predictions used.
            control_params: Control parameters actually used (snapshot).

        Returns:
            True if successfully saved, False otherwise.
        """
        try:
            # Create outcome document
            mission_outcome = {
                "mission_id": mission_id,
                "timestamp_ms": int(time.time() * 1000),
                "status": "success" if success else "failure",
                "time_to_goal_s": time_to_goal_s,
                "collisions": collisions,
                "blocked_time_s": blocked_time_s,
                "composite_score": composite_score,
            }

            # Add prediction info if available
            if predicted_from_episode:
                mission_outcome["predicted_from_episode"] = predicted_from_episode
            if similarity_score is not None:
                mission_outcome["similarity_score"] = similarity_score
            if control_params:
                mission_outcome["control_params"] = control_params

            # Save to file
            outcome_file = self.episodic_memory_dir / f"mission_outcome_{mission_id}.json"
            with open(outcome_file, 'w') as f:
                json.dump(mission_outcome, f, indent=2)

            logger.info(f"✓ Saved mission outcome: {outcome_file.name}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to save mission outcome: {e}")
            return False


# Standalone script usage
if __name__ == "__main__":
    import sys
    from argparse import ArgumentParser

    parser = ArgumentParser(description="SLAMOBridge - File-based SLAMO-EpisodicImprover interface")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # write-mission-initial
    cmd_write = subparsers.add_parser("write-mission-initial", help="Write mission_initial file")
    cmd_write.add_argument("--mission-id", required=True)
    cmd_write.add_argument("--start-x", type=float, required=True)
    cmd_write.add_argument("--start-y", type=float, required=True)
    cmd_write.add_argument("--end-x", type=float, required=True)
    cmd_write.add_argument("--end-y", type=float, required=True)
    cmd_write.add_argument("--estimated-distance", type=float, required=True)
    cmd_write.add_argument("--obstacle-density", type=float, required=True)
    cmd_write.add_argument("--memory-dir", default="episodic_memory")

    # wait-predictions
    cmd_wait = subparsers.add_parser("wait-predictions", help="Wait for predictions")
    cmd_wait.add_argument("--mission-id", required=True)
    cmd_wait.add_argument("--timeout", type=float, default=5.0)
    cmd_wait.add_argument("--memory-dir", default="episodic_memory")

    # get-predictions
    cmd_get = subparsers.add_parser("get-predictions", help="Get predictions (write + wait)")
    cmd_get.add_argument("--mission-id", required=True)
    cmd_get.add_argument("--start-x", type=float, required=True)
    cmd_get.add_argument("--start-y", type=float, required=True)
    cmd_get.add_argument("--end-x", type=float, required=True)
    cmd_get.add_argument("--end-y", type=float, required=True)
    cmd_get.add_argument("--estimated-distance", type=float, required=True)
    cmd_get.add_argument("--obstacle-density", type=float, required=True)
    cmd_get.add_argument("--timeout", type=float, default=5.0)
    cmd_get.add_argument("--memory-dir", default="episodic_memory")

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    bridge = SLAMOBridge(args.memory_dir if hasattr(args, 'memory_dir') else "episodic_memory")

    if args.command == "write-mission-initial":
        mission = MissionInitial(
            mission_id=args.mission_id,
            start_x=args.start_x,
            start_y=args.start_y,
            end_x=args.end_x,
            end_y=args.end_y,
            estimated_distance=args.estimated_distance,
            obstacle_density=args.obstacle_density,
        )
        success = bridge.write_mission_initial(mission)
        sys.exit(0 if success else 1)

    elif args.command == "wait-predictions":
        pred = bridge.wait_predictions(args.mission_id, timeout_s=args.timeout)
        if pred:
            print(json.dumps(pred.to_dict(), indent=2))
            sys.exit(0)
        else:
            sys.exit(1)

    elif args.command == "get-predictions":
        pred = bridge.get_predictions(
            start_x=args.start_x,
            start_y=args.start_y,
            end_x=args.end_x,
            end_y=args.end_y,
            obstacle_density=args.obstacle_density,
            estimated_distance=args.estimated_distance,
            mission_id=args.mission_id,
            timeout_s=args.timeout,
        )
        if pred:
            print(json.dumps(pred.to_dict(), indent=2))
            sys.exit(0)
        else:
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)
