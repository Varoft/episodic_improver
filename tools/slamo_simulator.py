#!/usr/bin/env python3
"""
SLAMO simulator for the ep_*.json lifecycle.

Usage:
  - start: create a start-only ep_*.json
  - complete: update an existing ep_*.json with outcome fields
"""

import argparse
import json
import random
import time
from pathlib import Path


def _load_json(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _save_json(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _make_episode_id() -> str:
    return f"ep_{int(time.time() * 1000)}"


def _random_point(min_val: float, max_val: float) -> float:
    return random.uniform(min_val, max_val)


def start_episode(args: argparse.Namespace) -> None:
    episodic_memory = Path(args.episodic_memory)
    episodic_memory.mkdir(parents=True, exist_ok=True)

    episode_id = args.episode_id or _make_episode_id()
    episode_path = episodic_memory / f"{episode_id}.json"

    episode = {
        "episode_id": episode_id,
        "start_ts_ms": str(int(time.time() * 1000)),
        "status": "running",
        "mission": {
            "controller_version": args.controller_version or "",
            "furniture_hash": args.furniture_hash or "",
            "map_layout_id": args.map_layout_id or "",
            "mission_type": args.mission_type or "goto_point",
            "robot_context": args.robot_context or ""
        },
        "source": {
            "x": args.src_x,
            "y": args.src_y,
            "obstacle_density": args.obstacle_density
        },
        "target": {
            "target_mode": "point",
            "target_x": args.target_x,
            "target_y": args.target_y,
            "target_object_id": ""
        }
    }

    _save_json(episode_path, episode)
    print(f"Created start-only episode: {episode_path}")


def random_episode(args: argparse.Namespace) -> None:
    episodic_memory = Path(args.episodic_memory)
    episodic_memory.mkdir(parents=True, exist_ok=True)

    if args.seed is not None:
        random.seed(args.seed)

    min_xy = -40.0
    max_xy = 40.0
    min_dist = 2.0

    for _ in range(100):
        src_x = _random_point(min_xy, max_xy)
        src_y = _random_point(min_xy, max_xy)
        target_x = _random_point(min_xy, max_xy)
        target_y = _random_point(min_xy, max_xy)

        dx = target_x - src_x
        dy = target_y - src_y
        straight_dist = (dx ** 2 + dy ** 2) ** 0.5
        if straight_dist >= min_dist:
            break
    else:
        raise SystemExit("Failed to generate a valid random mission")

    obstacle_density = random.uniform(0.05, 0.8)

    episode_id = args.episode_id or _make_episode_id()
    episode_path = episodic_memory / f"{episode_id}.json"

    episode = {
        "episode_id": episode_id,
        "start_ts_ms": str(int(time.time() * 1000)),
        "status": "running",
        "mission": {
            "controller_version": "",
            "furniture_hash": "",
            "map_layout_id": "",
            "mission_type": "goto_point",
            "robot_context": ""
        },
        "source": {
            "x": src_x,
            "y": src_y,
            "obstacle_density": obstacle_density
        },
        "target": {
            "target_mode": "point",
            "target_x": target_x,
            "target_y": target_y,
            "target_object_id": ""
        }
    }

    _save_json(episode_path, episode)
    print(f"Created random start-only episode: {episode_path}")


def complete_episode(args: argparse.Namespace) -> None:
    episode_path = Path(args.episode_path)
    if not episode_path.exists():
        raise SystemExit(f"Episode file not found: {episode_path}")

    episode = _load_json(episode_path)

    start_ts_ms = episode.get("start_ts_ms")
    end_ts_ms = str(int(time.time() * 1000))

    duration_s = args.duration_s
    if duration_s is None and start_ts_ms is not None:
        try:
            duration_s = (int(end_ts_ms) - int(start_ts_ms)) / 1000.0
        except ValueError:
            duration_s = None

    if duration_s is not None:
        episode["duration_s"] = duration_s
    episode["end_ts_ms"] = end_ts_ms
    episode["status"] = "success" if args.success else "failure"

    outcome = episode.get("outcome", {})
    outcome.update({
        "success_binary": 1 if args.success else 0,
        "time_to_goal_s": args.time_to_goal_s or duration_s or 0.0,
        "composite_score": args.composite_score if args.composite_score is not None else 0.0,
        "efficiency_score": args.efficiency_score if args.efficiency_score is not None else 0.0,
        "safety_score": args.safety_score if args.safety_score is not None else 0.0,
        "comfort_jerk_score": args.comfort_score if args.comfort_score is not None else 0.0
    })
    episode["outcome"] = outcome

    safety = episode.get("safety", {})
    safety.update({
        "n_collision": args.collisions,
        "blocked_time_s": args.blocked_time_s
    })
    episode["safety"] = safety

    trajectory = episode.get("trajectory", {})
    if args.distance_traveled_m is not None:
        trajectory["distance_traveled_m"] = args.distance_traveled_m
    if args.path_efficiency is not None:
        trajectory["path_efficiency"] = args.path_efficiency
    episode["trajectory"] = trajectory

    params_snapshot = episode.get("params_snapshot")
    if args.params_file:
        params_path = Path(args.params_file)
        params_snapshot = _load_json(params_path)
    elif params_snapshot is None and "prediction" in episode:
        params_snapshot = episode["prediction"].get("predicted_params")

    if params_snapshot is not None:
        episode["params_snapshot"] = params_snapshot

    _save_json(episode_path, episode)
    print(f"Updated episode with outcome: {episode_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SLAMO ep_*.json simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create start-only ep_*.json")
    start.add_argument("--episodic-memory", default="episodic_memory")
    start.add_argument("--episode-id", default=None)
    start.add_argument("--src-x", type=float, required=True)
    start.add_argument("--src-y", type=float, required=True)
    start.add_argument("--target-x", type=float, required=True)
    start.add_argument("--target-y", type=float, required=True)
    start.add_argument("--obstacle-density", type=float, default=0.0)
    start.add_argument("--mission-type", default="goto_point")
    start.add_argument("--controller-version", default="")
    start.add_argument("--furniture-hash", default="")
    start.add_argument("--map-layout-id", default="")
    start.add_argument("--robot-context", default="")
    start.set_defaults(func=start_episode)

    complete = subparsers.add_parser("complete", help="Finalize ep_*.json with outcome")
    complete.add_argument("episode_path")
    complete.add_argument("--success", action="store_true")
    complete.add_argument("--time-to-goal-s", type=float, default=None)
    complete.add_argument("--duration-s", type=float, default=None)
    complete.add_argument("--composite-score", type=float, default=None)
    complete.add_argument("--efficiency-score", type=float, default=None)
    complete.add_argument("--safety-score", type=float, default=None)
    complete.add_argument("--comfort-score", type=float, default=None)
    complete.add_argument("--collisions", type=int, default=0)
    complete.add_argument("--blocked-time-s", type=float, default=0.0)
    complete.add_argument("--distance-traveled-m", type=float, default=None)
    complete.add_argument("--path-efficiency", type=float, default=None)
    complete.add_argument("--params-file", default=None)
    complete.set_defaults(func=complete_episode)

    random_cmd = subparsers.add_parser("random", help="Create random start-only ep_*.json")
    random_cmd.add_argument("--episodic-memory", default="episodic_memory")
    random_cmd.add_argument("--episode-id", default=None)
    random_cmd.add_argument("--seed", type=int, default=None)
    random_cmd.set_defaults(func=random_episode)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
