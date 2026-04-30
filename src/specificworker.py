#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2026 by YOUR NAME HERE
#
#    This file is part of RoboComp
#
#    RoboComp is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    RoboComp is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with RoboComp.  If not, see <http://www.gnu.org/licenses/>.
#

import json
import logging
import shutil
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from rich.console import Console
from genericworker import *
import interfaces as ifaces

sys.path.append('/opt/robocomp/lib')
console = Console(highlight=False)
logger = logging.getLogger(__name__)

try:
    from .config_manager import ConfigManager
    from .directory_monitor import DirectoryMonitor, MonitorConfig
    from .episodic_improver import MissionSpec
    from .fingerprint_extractor import FingerprintExtractor
    from .recommendation_engine import RecommendationEngine, RecommendationEngineConfig
except ImportError:
    from config_manager import ConfigManager
    from directory_monitor import DirectoryMonitor, MonitorConfig
    from episodic_improver import MissionSpec
    from fingerprint_extractor import FingerprintExtractor
    from recommendation_engine import RecommendationEngine, RecommendationEngineConfig


class SpecificWorker(GenericWorker):
    def __init__(self, proxy_map, configData, startup_check=False):
        super(SpecificWorker, self).__init__(proxy_map, configData)
        self.Period = configData["Period"]["Compute"]
        self._monitor = None
        self._processed_dir = None
        self._engine = None
        self._index_path = None
        self._fingerprint_extractor = FingerprintExtractor()
        self._setup_monitoring()
        if startup_check:
            self.startup_check()
        else:
            self.timer.timeout.connect(self.compute)
            self.timer.start(self.Period)

    def __del__(self):
        """Destructor"""
        if self._monitor:
            self._monitor.stop()

    def _setup_monitoring(self) -> None:
        config_mgr = ConfigManager()
        config_mgr.load()
        config = config_mgr.get()

        episodic_memory_dir = Path(config.directories.episodic_memory_dir)
        self._processed_dir = episodic_memory_dir / "processed"
        self._processed_dir.mkdir(parents=True, exist_ok=True)

        self._index_path = episodic_memory_dir / "fingerprints_index_unified_7d.json"
        legacy_index = Path("episodic_memory_7d_legacy") / "fingerprints_index_unified_7d.json"

        if not self._index_path.exists() and legacy_index.exists():
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(legacy_index, self._index_path)
            logger.info(f"Copied legacy index to {self._index_path}")

        engine_config = RecommendationEngineConfig(
            fingerprint_index_path=None,
            outcome_quality_threshold=config.fingerprint.outcome_quality_threshold,
            k_neighbors=config.fingerprint.k_neighbors,
        )
        self._engine = RecommendationEngine(engine_config)

        if not self._index_path.exists():
            logger.error(f"7D index not found at {self._index_path}")
        else:
            enabled = self._engine.enable_7d_system(self._index_path)
            if not enabled:
                logger.error("7D system failed to initialize")
            else:
                legacy_root = Path("episodic_memory_7d_legacy")
                if legacy_root.exists():
                    self._engine.improver_7d.index_manager.set_base_dir(legacy_root)

        monitor_config = MonitorConfig(
            episodic_memory_dir=episodic_memory_dir,
            query_dir=config.directories.query_dir,
            recommendations_dir=config.directories.recommendations_dir,
            ttl_seconds=config.monitoring.ttl_seconds,
            cleanup_interval_seconds=config.monitoring.cleanup_interval_seconds,
            recursive_watch=False,
        )

        self._monitor = DirectoryMonitor(monitor_config)
        self._monitor.register_episode_callback(self._on_episode_changed)
        self._monitor.start()

    def _on_episode_changed(self, episode_path: Path) -> None:
        if self._processed_dir and self._processed_dir in episode_path.parents:
            return

        episode_data = self._load_episode_json(episode_path)
        if not episode_data:
            return

        if self._is_completed_episode(episode_data):
            self._handle_completed_episode(episode_path, episode_data)
            return

        if self._has_prediction(episode_data):
            return

        self._handle_start_episode(episode_path, episode_data)

    def _load_episode_json(self, episode_path: Path) -> dict:
        try:
            with open(episode_path, 'r') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load {episode_path.name}: {e}")
            return {}

    @staticmethod
    def _is_completed_episode(episode_data: dict) -> bool:
        return bool(episode_data.get("outcome"))

    @staticmethod
    def _has_prediction(episode_data: dict) -> bool:
        prediction = episode_data.get("prediction")
        return bool(prediction and prediction.get("status") == "ready")

    def _handle_start_episode(self, episode_path: Path, episode_data: dict) -> None:
        if not self._engine or not self._engine.improver_7d:
            logger.warning("7D system not ready, skipping prediction")
            return

        source = episode_data.get("source", {})
        target = episode_data.get("target", {})

        src_x = source.get("x", 0.0)
        src_y = source.get("y", 0.0)
        target_x = target.get("target_x", 0.0)
        target_y = target.get("target_y", 0.0)
        obstacle_density = source.get("obstacle_density", episode_data.get("obstacle_density", 0.0))

        dx = target_x - src_x
        dy = target_y - src_y
        straight_dist = (dx ** 2 + dy ** 2) ** 0.5
        estimated_distance = episode_data.get("estimated_distance", straight_dist)

        mission_spec = MissionSpec(
            start_x=src_x,
            start_y=src_y,
            end_x=target_x,
            end_y=target_y,
            estimated_distance=estimated_distance,
            obstacle_density=obstacle_density,
        )

        query_id = episode_data.get("episode_id", episode_path.stem)
        prediction = self._engine.generate_recommendations_7d(query_id, mission_spec)

        if prediction.get("status") != "success":
            logger.warning(f"Prediction failed for {episode_path.name}: {prediction.get('status')}")
            return

        episode_data["prediction"] = {
            "status": "ready",
            "timestamp_ms": int(time.time() * 1000),
            "best_match_id": prediction.get("best_match_id"),
            "best_match_similarity": prediction.get("best_match_similarity"),
            "fingerprint_7d": prediction.get("fingerprint_7d", []),
            "predicted_params": prediction.get("predicted_parameters", {}),
            "search_results": prediction.get("recommendations", []),
            "perturbation": prediction.get("perturbation_details", {})
        }

        try:
            with open(episode_path, 'w') as f:
                json.dump(episode_data, f, indent=2)
            logger.info(f"Predictions written into {episode_path.name}")
        except OSError as e:
            logger.error(f"Failed to update {episode_path.name}: {e}")

    def _handle_completed_episode(self, episode_path: Path, episode_data: dict) -> None:
        if not self._engine or not self._engine.improver_7d:
            logger.warning("7D system not ready, skipping post-mission evaluation")
            return

        outcome = episode_data.get("outcome", {})
        safety = episode_data.get("safety", {})
        mission_outcome = {
            "success": outcome.get("success_binary", 1 if episode_data.get("status") == "success" else 0),
            "time_to_goal_s": outcome.get("time_to_goal_s", episode_data.get("duration_s", 0.0)),
            "collisions": safety.get("n_collision", 0),
            "blocked_time_s": safety.get("blocked_time_s", 0.0),
            "composite_score": outcome.get("composite_score")
        }

        self._engine.post_mission_evaluation_7d(mission_outcome)

        fp_raw = self._fingerprint_extractor.extract_7d_from_dict({
            "source": {
                "x": episode_data.get("source", {}).get("x", 0.0),
                "y": episode_data.get("source", {}).get("y", 0.0)
            },
            "target": {
                "target_x": episode_data.get("target", {}).get("target_x", 0.0),
                "target_y": episode_data.get("target", {}).get("target_y", 0.0)
            },
            "obstacle_density": episode_data.get("source", {}).get("obstacle_density", 0.0),
            "estimated_distance": episode_data.get(
                "estimated_distance",
                episode_data.get("trajectory", {}).get("distance_traveled_m", 0.0)
            )
        })

        index_entry = {
            "episode_id": episode_data.get("episode_id", episode_path.stem),
            "fingerprint_7d": fp_raw,
            "distance_traveled_m": episode_data.get("trajectory", {}).get("distance_traveled_m"),
            "params_snapshot": episode_data.get("params_snapshot", {}),
            "outcome": outcome
        }

        index_manager = self._engine.improver_7d.index_manager
        index_manager.add_episode_entry(index_entry, episode_path, folder_name="runtime")
        index_manager.save_index(str(self._index_path))

        self._move_to_processed(episode_path)

    def _move_to_processed(self, episode_path: Path) -> None:
        if not self._processed_dir:
            return

        target_path = self._processed_dir / episode_path.name
        if target_path.exists():
            stamp = int(time.time() * 1000)
            target_path = self._processed_dir / f"{episode_path.stem}_{stamp}.json"

        try:
            shutil.move(str(episode_path), str(target_path))
            logger.info(f"Moved completed mission to {target_path.name}")
        except OSError as e:
            logger.error(f"Failed to move {episode_path.name}: {e}")


    @QtCore.Slot()
    def compute(self):
        return True

    def startup_check(self):
        QTimer.singleShot(200, QApplication.instance().quit)






