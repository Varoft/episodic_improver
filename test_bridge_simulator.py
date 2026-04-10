#!/usr/bin/env python3
"""
test_bridge_simulator.py: Integration tests for PRE-MISIÓN protocol.

FASE 2: Testing validation
- Simulates SLAMO behavior (writes mission_initial_*.json)
- Verifies episodic_improver generates predictions
- Measures latency and correctness
- Validates round-trip protocol

Usage:
    python test_bridge_simulator.py simulate --count 5
    python test_bridge_simulator.py latency --iterations 20
    python test_bridge_simulator.py stress --missions 50 --duration 30
    python test_bridge_simulator.py validate
"""

import json
import logging
import time
import sys
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple
from argparse import ArgumentParser
import statistics

# Import from episodic_improver package
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from slamo_bridge import SLAMOBridge, MissionInitial, PredictionResult
except ImportError:
    print("Error: Cannot import slamo_bridge. Make sure to run from episodic_improver directory.")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test mission."""
    mission_id: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    estimated_distance: float
    obstacle_density: float
    write_time_ms: float
    prediction_received: bool
    prediction_latency_ms: Optional[float]
    best_match_id: Optional[str]
    similarity: Optional[float]
    num_params: int
    error: Optional[str]


class TestBridgeSimulator:
    """Simulates SLAMO and validates episodic_improver predictions."""

    def __init__(self, episodic_memory_dir: str = "episodic_memory"):
        """Initialize simulator."""
        self.bridge = SLAMOBridge(episodic_memory_dir)
        self.episodic_memory_dir = Path(episodic_memory_dir)
        self.results: List[TestResult] = []

    def generate_test_mission(
        self, 
        mission_num: int,
        start_pos: Optional[Tuple[float, float]] = None,
        end_pos: Optional[Tuple[float, float]] = None,
    ) -> Tuple[float, float, float, float, float, float]:
        """
        Generate a random/deterministic test mission.

        Args:
            mission_num: Mission number for deterministic seed.
            start_pos: Optional override for start position.
            end_pos: Optional override for end position.

        Returns:
            Tuple of (start_x, start_y, end_x, end_y, est_distance, obstacle_density)
        """
        # Use mission number as seed for reproducibility
        seed = mission_num * 17
        
        # Default positions (can be overridden)
        if start_pos is None:
            start_x = (seed % 40) * 2 - 40  # [-40, 40]
            start_y = ((seed // 40) % 40) * 2 - 40
        else:
            start_x, start_y = start_pos

        if end_pos is None:
            end_x = ((seed + 13) % 40) * 2 - 40
            end_y = ((seed + 31) % 40) * 2 - 40
        else:
            end_x, end_y = end_pos

        # Compute distance and density
        import math
        straight_dist = math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
        estimated_distance = straight_dist * (1.0 + (seed % 50) / 200.0)  # Add 0-25% detour
        obstacle_density = (seed % 100) / 200.0  # [0, 0.5]

        return start_x, start_y, end_x, end_y, estimated_distance, obstacle_density

    def simulate_single_mission(
        self,
        mission_num: int,
        timeout_s: float = 5.0,
    ) -> TestResult:
        """
        Simulate a single mission: write + wait for predictions.

        Args:
            mission_num: Mission number (for ID generation).
            timeout_s: Timeout in seconds for predictions.

        Returns:
            TestResult with metrics and outcome.
        """
        mission_id = f"test_mission_{mission_num:03d}_{int(time.time() * 1000) % 10000}"
        
        try:
            # Generate test mission
            start_x, start_y, end_x, end_y, est_dist, obs_dens = self.generate_test_mission(mission_num)

            logger.info(f"\n[MISSION {mission_num}] {mission_id}")
            logger.info(f"  Geometry: ({start_x:.1f}, {start_y:.1f}) → ({end_x:.1f}, {end_y:.1f})")
            logger.info(f"  Est. distance: {est_dist:.1f}m, Obstacle density: {obs_dens:.2f}")

            # (1) Write mission_initial
            write_start = time.time()
            mission = MissionInitial(
                mission_id=mission_id,
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
                estimated_distance=est_dist,
                obstacle_density=obs_dens,
            )
            success = self.bridge.write_mission_initial(mission)
            write_time_ms = (time.time() - write_start) * 1000

            if not success:
                return TestResult(
                    mission_id=mission_id,
                    start_x=start_x, start_y=start_y,
                    end_x=end_x, end_y=end_y,
                    estimated_distance=est_dist,
                    obstacle_density=obs_dens,
                    write_time_ms=write_time_ms,
                    prediction_received=False,
                    prediction_latency_ms=None,
                    best_match_id=None,
                    similarity=None,
                    num_params=0,
                    error="Failed to write mission_initial"
                )

            logger.info(f"  ✓ Wrote mission_initial ({write_time_ms:.1f}ms)")

            # (2) Wait for predictions
            predict_start = time.time()
            predictions = self.bridge.wait_predictions(mission_id, timeout_s=timeout_s)
            predict_latency_ms = (time.time() - predict_start) * 1000

            if predictions is None:
                logger.warning(f"  ✗ No predictions received (timeout after {timeout_s}s)")
                return TestResult(
                    mission_id=mission_id,
                    start_x=start_x, start_y=start_y,
                    end_x=end_x, end_y=end_y,
                    estimated_distance=est_dist,
                    obstacle_density=obs_dens,
                    write_time_ms=write_time_ms,
                    prediction_received=False,
                    prediction_latency_ms=predict_latency_ms,
                    best_match_id=None,
                    similarity=None,
                    num_params=0,
                    error="Timeout"
                )

            if predictions.status != "ready":
                logger.warning(f"  ⚠ Predictions status: {predictions.status}")
                return TestResult(
                    mission_id=mission_id,
                    start_x=start_x, start_y=start_y,
                    end_x=end_x, end_y=end_y,
                    estimated_distance=est_dist,
                    obstacle_density=obs_dens,
                    write_time_ms=write_time_ms,
                    prediction_received=False,
                    prediction_latency_ms=predict_latency_ms,
                    best_match_id=predictions.best_match_id,
                    similarity=predictions.best_match_similarity,
                    num_params=len(predictions.predicted_parameters),
                    error=f"Status: {predictions.status}"
                )

            # (3) Validate predictions
            logger.info(f"  ✓ Predictions received ({predict_latency_ms:.1f}ms)")
            logger.info(f"    Best match: {predictions.best_match_id} (similarity: {predictions.best_match_similarity:.1%})")
            logger.info(f"    Predicted params: {len(predictions.predicted_parameters)}")
            
            for param_name, param_value in list(predictions.predicted_parameters.items())[:3]:
                logger.info(f"      - {param_name}: {param_value:.4f}")
            
            if len(predictions.predicted_parameters) > 3:
                logger.info(f"      ... and {len(predictions.predicted_parameters) - 3} more")

            return TestResult(
                mission_id=mission_id,
                start_x=start_x, start_y=start_y,
                end_x=end_x, end_y=end_y,
                estimated_distance=est_dist,
                obstacle_density=obs_dens,
                write_time_ms=write_time_ms,
                prediction_received=True,
                prediction_latency_ms=predict_latency_ms,
                best_match_id=predictions.best_match_id,
                similarity=predictions.best_match_similarity,
                num_params=len(predictions.predicted_parameters),
                error=None,
            )

        except Exception as e:
            logger.error(f"  ✗ Exception: {e}")
            import traceback
            traceback.print_exc()
            return TestResult(
                mission_id=mission_id,
                start_x=0, start_y=0,
                end_x=0, end_y=0,
                estimated_distance=0,
                obstacle_density=0,
                write_time_ms=0,
                prediction_received=False,
                prediction_latency_ms=None,
                best_match_id=None,
                similarity=None,
                num_params=0,
                error=str(e),
            )

    def print_summary(self, results: List[TestResult]) -> None:
        """Print summary statistics."""
        if not results:
            logger.info("No results to summarize.")
            return

        successful = [r for r in results if r.prediction_received and r.error is None]
        failed = [r for r in results if r.error is not None]
        timeouts = [r for r in results if r.prediction_latency_ms and r.error == "Timeout"]

        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total missions: {len(results)}")
        logger.info(f"✓ Successful: {len(successful)}/{len(results)}")
        logger.info(f"✗ Failed: {len(failed)}/{len(results)}")
        logger.info(f"⏱ Timeouts: {len(timeouts)}/{len(results)}")

        if successful:
            latencies = [r.prediction_latency_ms for r in successful if r.prediction_latency_ms]
            similarities = [r.similarity for r in successful if r.similarity]
            
            logger.info(f"\nLatency Statistics (successful predictions):")
            logger.info(f"  Mean: {statistics.mean(latencies):.1f}ms")
            logger.info(f"  Median: {statistics.median(latencies):.1f}ms")
            logger.info(f"  Min: {min(latencies):.1f}ms")
            logger.info(f"  Max: {max(latencies):.1f}ms")
            logger.info(f"  Stdev: {statistics.stdev(latencies) if len(latencies) > 1 else 0:.1f}ms")

            logger.info(f"\nSimilarity Statistics:")
            logger.info(f"  Mean: {statistics.mean(similarities):.1%}")
            logger.info(f"  Median: {statistics.median(similarities):.1%}")
            logger.info(f"  Min: {min(similarities):.1%}")
            logger.info(f"  Max: {max(similarities):.1%}")

        if failed:
            logger.info(f"\nFailure Breakdown:")
            for error_type in set(r.error for r in failed):
                count = len([r for r in failed if r.error == error_type])
                logger.info(f"  {error_type}: {count}")

        logger.info("=" * 70 + "\n")

    def run_simulate(self, count: int = 5, delay_s: float = 1.0):
        """
        PHASE 1 TEST: Simulate N missions sequentially.

        Args:
            count: Number of missions to simulate.
            delay_s: Delay between missions (to avoid queue buildup).
        """
        logger.info(f"\n{'*' * 70}")
        logger.info(f"SIMULATE TEST: {count} missions")
        logger.info(f"{'*' * 70}")

        for mission_num in range(1, count + 1):
            result = self.simulate_single_mission(mission_num)
            self.results.append(result)
            
            if mission_num < count:
                logger.info(f"Waiting {delay_s}s before next mission...")
                time.sleep(delay_s)

        self.print_summary(self.results)

    def run_latency(self, iterations: int = 20):
        """
        PHASE 2 TEST: Measure latency for rapid-fire missions.

        Args:
            iterations: Number of missions to measure.
        """
        logger.info(f"\n{'*' * 70}")
        logger.info(f"LATENCY TEST: {iterations} rapid-fire missions")
        logger.info(f"{'*' * 70}")

        for mission_num in range(1, iterations + 1):
            result = self.simulate_single_mission(mission_num, timeout_s=10.0)
            self.results.append(result)

        self.print_summary(self.results)

    def run_stress(self, missions: int = 50, duration_s: int = 30):
        """
        PHASE 3 TEST: Stress test with many concurrent missions.

        Args:
            missions: Number of concurrent missions.
            duration_s: How long to sustain stress (not implemented yet).
        """
        logger.info(f"\n{'*' * 70}")
        logger.info(f"STRESS TEST: {missions} missions (max {duration_s}s)")
        logger.info(f"{'*' * 70}")

        for mission_num in range(1, missions + 1):
            result = self.simulate_single_mission(mission_num, timeout_s=10.0)
            self.results.append(result)

        self.print_summary(self.results)

    def run_validate(self):
        """
        Validation test: Check protocol compliance.
        """
        logger.info(f"\n{'*' * 70}")
        logger.info(f"VALIDATE TEST: Protocol compliance check")
        logger.info(f"{'*' * 70}")

        # Check that files are being created
        mission_initial_files = list(self.episodic_memory_dir.glob("mission_initial_*.json"))
        predictions_files = list(self.episodic_memory_dir.glob("predictions_*.json"))

        logger.info(f"Directory: {self.episodic_memory_dir}")
        logger.info(f"mission_initial_*.json files: {len(mission_initial_files)}")
        logger.info(f"predictions_*.json files: {len(predictions_files)}")

        # Validate format of existing files
        for mission_file in mission_initial_files[-3:]:  # Last 3
            try:
                data = json.loads(mission_file.read_text())
                required_fields = ["mission_id", "start_x", "start_y", "end_x", "end_y", 
                                 "estimated_distance", "obstacle_density"]
                missing = [f for f in required_fields if f not in data]
                if missing:
                    logger.warning(f"  {mission_file.name}: missing fields {missing}")
                else:
                    logger.info(f"  ✓ {mission_file.name}: valid")
            except json.JSONDecodeError as e:
                logger.warning(f"  {mission_file.name}: invalid JSON ({e})")

        for pred_file in predictions_files[-3:]:  # Last 3
            try:
                data = json.loads(pred_file.read_text())
                required_fields = ["mission_id", "status", "best_match_id", "predicted_parameters"]
                missing = [f for f in required_fields if f not in data]
                if missing:
                    logger.warning(f"  {pred_file.name}: missing fields {missing}")
                else:
                    logger.info(f"  ✓ {pred_file.name}: valid (status={data['status']})")
            except json.JSONDecodeError as e:
                logger.warning(f"  {pred_file.name}: invalid JSON ({e})")


def main():
    """Entry point."""
    parser = ArgumentParser(description="Test PRE-MISIÓN Protocol")
    subparsers = parser.add_subparsers(dest="command", help="Test command")

    # simulate
    cmd_sim = subparsers.add_parser("simulate", help="Simulate N missions")
    cmd_sim.add_argument("--count", type=int, default=5, help="Number of missions")
    cmd_sim.add_argument("--delay", type=float, default=1.0, help="Delay between missions (s)")
    cmd_sim.add_argument("--memory-dir", default="episodic_memory")

    # latency
    cmd_lat = subparsers.add_parser("latency", help="Measure latency")
    cmd_lat.add_argument("--iterations", type=int, default=20, help="Number of iterations")
    cmd_lat.add_argument("--memory-dir", default="episodic_memory")

    # stress
    cmd_stress = subparsers.add_parser("stress", help="Stress test")
    cmd_stress.add_argument("--missions", type=int, default=50, help="Number of missions")
    cmd_stress.add_argument("--duration", type=int, default=30, help="Duration (s)")
    cmd_stress.add_argument("--memory-dir", default="episodic_memory")

    # validate
    cmd_val = subparsers.add_parser("validate", help="Validate protocol compliance")
    cmd_val.add_argument("--memory-dir", default="episodic_memory")

    args = parser.parse_args()

    # Get memory dir
    memory_dir = getattr(args, 'memory_dir', 'episodic_memory')

    simulator = TestBridgeSimulator(memory_dir)

    if args.command == "simulate":
        simulator.run_simulate(count=args.count, delay_s=args.delay)
    elif args.command == "latency":
        simulator.run_latency(iterations=args.iterations)
    elif args.command == "stress":
        simulator.run_stress(missions=args.missions, duration_s=args.duration)
    elif args.command == "validate":
        simulator.run_validate()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
