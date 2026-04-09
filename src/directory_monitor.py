#!/usr/bin/env python3
"""
directory_monitor.py: Directory monitoring for episodic memory and queries.

Monitors:
- episodic_memory/<location>/ for new episode JSON files
- etc/ for query_pending.json files
- Cleanup of orphaned recommendations_*.json files (TTL-based)
"""

import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional, List
from threading import Thread, Event

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent


logger = logging.getLogger(__name__)


@dataclass
class MonitorConfig:
    """Configuration for directory monitoring."""
    episodic_memory_dir: Path  # Base directory for episodic memory
    query_dir: Path             # Directory where query_pending.json appears
    recommendations_dir: Path   # Directory for recommendations output
    ttl_seconds: int = 300      # TTL for orphaned recommendation files (5 min)
    cleanup_interval_seconds: int = 60  # How often to cleanup (1 min)


class EpisodeEventHandler(FileSystemEventHandler):
    """Handles file events in episodic memory directories."""
    
    def __init__(self, on_episode_create: Callable[[Path], None]):
        """
        Initialize handler.
        
        Args:
            on_episode_create: Callback when new episode JSON is detected.
        """
        super().__init__()
        self.on_episode_create = on_episode_create
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Only interested in JSON episode files
        if path.suffix == ".json" and path.name.startswith("ep_"):
            logger.info(f"New episode detected: {path.name}")
            self.on_episode_create(path)


class QueryEventHandler(FileSystemEventHandler):
    """Handles file events for query files."""
    
    def __init__(self, on_query_create: Callable[[Path], None]):
        """
        Initialize handler.
        
        Args:
            on_query_create: Callback when query_pending.json is detected.
        """
        super().__init__()
        self.on_query_create = on_query_create
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        
        # Only interested in query_pending.json
        if path.name == "query_pending.json":
            logger.info(f"New query detected: {path}")
            self.on_query_create(path)


class DirectoryMonitor:
    """
    Monitors episodic memory and query directories.
    
    - Detects new episodes and triggers callbacks
    - Detects queries and triggers callbacks
    - Periodically cleans up orphaned recommendation files (TTL-based)
    """
    
    def __init__(self, config: MonitorConfig):
        """
        Initialize monitor.
        
        Args:
            config: MonitorConfig with directory and TTL settings.
        """
        self.config = config
        self.observer = Observer()
        self.episode_handlers: List[EpisodeEventHandler] = []
        self.query_handlers: List[QueryEventHandler] = []
        self._stop_event = Event()
        self._cleanup_thread: Optional[Thread] = None
        
        logger.info(
            f"DirectoryMonitor initialized:\n"
            f"  episodic_memory: {config.episodic_memory_dir}\n"
            f"  query_dir: {config.query_dir}\n"
            f"  recommendations: {config.recommendations_dir}\n"
            f"  TTL: {config.ttl_seconds}s"
        )
    
    def register_episode_callback(self, callback: Callable[[Path], None]) -> None:
        """
        Register callback for new episodes.
        
        Args:
            callback: Function(path: Path) called when episode detected.
        """
        handler = EpisodeEventHandler(callback)
        self.episode_handlers.append(handler)
    
    def register_query_callback(self, callback: Callable[[Path], None]) -> None:
        """
        Register callback for new queries.
        
        Args:
            callback: Function(path: Path) called when query detected.
        """
        handler = QueryEventHandler(callback)
        self.query_handlers.append(handler)
    
    def start(self) -> None:
        """Start monitoring directories."""
        # Create directories if they don't exist
        self.config.episodic_memory_dir.mkdir(parents=True, exist_ok=True)
        self.config.query_dir.mkdir(parents=True, exist_ok=True)
        self.config.recommendations_dir.mkdir(parents=True, exist_ok=True)
        
        # Register episode handlers recursively for episodic_memory_dir
        # This watches all subdirectories for episode files
        if self.episode_handlers:
            for handler in self.episode_handlers:
                self.observer.schedule(
                    handler,
                    str(self.config.episodic_memory_dir),
                    recursive=True
                )
            logger.info(
                f"Registered episode monitoring for: "
                f"{self.config.episodic_memory_dir} (recursive)"
            )
        
        # Register query handlers
        if self.query_handlers:
            for handler in self.query_handlers:
                self.observer.schedule(handler, str(self.config.query_dir), recursive=False)
            logger.info(f"Registered query monitoring in: {self.config.query_dir}")
        
        # Start observer
        self.observer.start()
        logger.info("DirectoryMonitor started")
        
        # Start cleanup thread
        self._stop_event.clear()
        self._cleanup_thread = Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def stop(self) -> None:
        """Stop monitoring directories."""
        logger.info("Stopping DirectoryMonitor...")
        self._stop_event.set()
        self.observer.stop()
        self.observer.join(timeout=5)
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("DirectoryMonitor stopped")
    
    def _cleanup_loop(self) -> None:
        """
        Periodic cleanup loop for orphaned recommendation files.
        
        Removes recommendations_*.json files older than TTL.
        """
        while not self._stop_event.is_set():
            try:
                self._cleanup_orphaned_files()
                self._stop_event.wait(self.config.cleanup_interval_seconds)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def _cleanup_orphaned_files(self) -> None:
        """Remove orphaned recommendation files based on TTL."""
        now = time.time()
        
        for reco_file in self.config.recommendations_dir.glob("recommendations_*.json"):
            # Check if file is older than TTL
            file_age = now - reco_file.stat().st_mtime
            
            if file_age > self.config.ttl_seconds:
                try:
                    logger.info(
                        f"Removing orphaned recommendation file (age={file_age:.0f}s): "
                        f"{reco_file.name}"
                    )
                    reco_file.unlink()
                except OSError as e:
                    logger.error(f"Failed to remove {reco_file.name}: {e}")
    
    @staticmethod
    def load_query_pending(query_file: Path) -> Optional[dict]:
        """
        Load query_pending.json file.
        
        Args:
            query_file: Path to query_pending.json
        
        Returns:
            Parsed JSON dict or None if invalid.
        """
        try:
            with open(query_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded query from {query_file.name}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load query: {e}")
            return None
    
    @staticmethod
    def load_episode(episode_file: Path) -> Optional[dict]:
        """
        Load episode JSON file.
        
        Args:
            episode_file: Path to episode_*.json
        
        Returns:
            Parsed JSON dict or None if invalid.
        """
        try:
            with open(episode_file, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded episode from {episode_file.name}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load episode: {e}")
            return None
    
    @staticmethod
    def save_recommendation(
        query_id: str,
        recommendation_data: dict,
        output_dir: Path
    ) -> Path:
        """
        Save recommendation result to recommendations_<query_id>.json.
        
        Args:
            query_id: Query identifier.
            recommendation_data: Data to save.
            output_dir: Directory for output files.
        
        Returns:
            Path to saved file.
        """
        output_file = output_dir / f"recommendations_{query_id}.json"
        
        try:
            with open(output_file, 'w') as f:
                json.dump(recommendation_data, f, indent=2)
            logger.info(f"Saved recommendations to {output_file.name}")
            return output_file
        except OSError as e:
            logger.error(f"Failed to save recommendations: {e}")
            raise


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure monitoring
    config = MonitorConfig(
        episodic_memory_dir=Path("/tmp/episodic_memory"),
        query_dir=Path("/tmp/queries"),
        recommendations_dir=Path("/tmp/recommendations"),
        ttl_seconds=30,
        cleanup_interval_seconds=10
    )
    
    monitor = DirectoryMonitor(config)
    
    # Register callbacks
    def on_episode(path: Path):
        print(f"[CALLBACK] New episode: {path.name}")
    
    def on_query(path: Path):
        print(f"[CALLBACK] New query: {path.name}")
    
    monitor.register_episode_callback(on_episode)
    monitor.register_query_callback(on_query)
    
    # Start monitoring
    monitor.start()
    
    try:
        # Test: create a query
        test_query = {
            "query_id": "test_001",
            "mission": {
                "start_x": 0.0,
                "start_y": -27.0,
                "end_x": 0.0,
                "end_y": 26.8,
                "estimated_distance": 54.0,
                "obstacle_density": 0.12
            }
        }
        config.query_dir.mkdir(parents=True, exist_ok=True)
        with open(config.query_dir / "query_pending.json", 'w') as f:
            json.dump(test_query, f)
        print("[TEST] Created query_pending.json")
        
        # Keep running for 15 seconds
        import time
        time.sleep(15)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        monitor.stop()
        print("Monitor stopped")
