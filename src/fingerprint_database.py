#!/usr/bin/env python3
"""
fingerprint_database.py: Persistent fingerprint database for episodic memory.

Manages a JSON database of all computed fingerprints, indexed by location.
Fingerprints are computed once when episodes are first encountered and cached
for fast retrieval and k-NN searches.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import time

try:
    from .episodic_improver import FingerprintModel, MissionSpec
except ImportError:
    from episodic_improver import FingerprintModel, MissionSpec


logger = logging.getLogger(__name__)


@dataclass
class FingerprintEntry:
    """Single fingerprint entry in the database."""
    episode_id: str
    location: str
    fingerprint: List[float]  # 9D fingerprint vector
    
    # Mission characteristics
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    estimated_distance: float
    obstacle_density: float
    
    # Quality scores
    efficiency_score: float
    safety_score: float
    smoothness_score: float
    outcome_quality: float
    
    # Outcome information
    success_binary: int
    time_to_goal_s: float
    composite_score: float
    
    # Parameters used
    params_snapshot: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    timestamp_ms: int = 0
    source_file: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FingerprintEntry":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class FingerprintDatabase:
    """Main fingerprint database."""
    version: str = "1.0"
    generated_at: str = ""
    fingerprints_by_location: Dict[str, List[FingerprintEntry]] = field(
        default_factory=dict
    )
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "fingerprints_by_location": {
                loc: [fp.to_dict() for fp in entries]
                for loc, entries in self.fingerprints_by_location.items()
            },
            "metadata": {
                "total_episodes": sum(
                    len(entries)
                    for entries in self.fingerprints_by_location.values()
                ),
                "locations": list(self.fingerprints_by_location.keys()),
                "last_updated": self.generated_at,
                **self.metadata,
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "FingerprintDatabase":
        """Create from dictionary."""
        db = cls(
            version=data.get("version", "1.0"),
            generated_at=data.get("generated_at", ""),
            metadata=data.get("metadata", {}),
        )
        for location, entries in data.get("fingerprints_by_location", {}).items():
            db.fingerprints_by_location[location] = [
                FingerprintEntry.from_dict(entry)
                for entry in entries
            ]
        return db


class FingerprintDatabaseManager:
    """Manages fingerprint database persistence and operations."""
    
    def __init__(
        self,
        database_file: Path = Path("etc/fingerprint_database.json"),
        fingerprint_model: Optional[FingerprintModel] = None,
    ):
        """
        Initialize database manager.
        
        Args:
            database_file: Path to JSON database file.
            fingerprint_model: FingerprintModel to use for computation.
                              If None, creates a new one with defaults.
        """
        self.database_file = Path(database_file)
        self.model = fingerprint_model or FingerprintModel()
        self.db = FingerprintDatabase()
        
        # Load existing database if available
        if self.database_file.exists():
            self.load()
        else:
            logger.info(f"Creating new fingerprint database at {self.database_file}")
    
    def load(self) -> bool:
        """
        Load database from JSON file.
        
        Returns:
            True if loaded successfully, False otherwise.
        """
        try:
            with open(self.database_file, "r") as f:
                data = json.load(f)
            self.db = FingerprintDatabase.from_dict(data)
            logger.info(
                f"Loaded fingerprint database with "
                f"{sum(len(e) for e in self.db.fingerprints_by_location.values())} episodes"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load fingerprint database: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save database to JSON file.
        
        Returns:
            True if saved successfully, False otherwise.
        """
        try:
            self.database_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Update timestamp
            self.db.generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            
            with open(self.database_file, "w") as f:
                json.dump(self.db.to_dict(), f, indent=2)
            
            logger.info(f"Saved fingerprint database to {self.database_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save fingerprint database: {e}")
            return False
    
    def add_episode(
        self,
        episode_id: str,
        location: str,
        episode_data: Dict,
    ) -> Optional[FingerprintEntry]:
        """
        Add episode to database (compute fingerprint if not already present).
        
        Args:
            episode_id: Unique episode identifier.
            location: Location/region identifier (e.g., "inicio_fin_pasillo").
            episode_data: Full episode JSON data from SLAMO.
        
        Returns:
            FingerprintEntry if successful, None otherwise.
        """
        # Check if already exists
        if location in self.db.fingerprints_by_location:
            existing = [
                fp for fp in self.db.fingerprints_by_location[location]
                if fp.episode_id == episode_id
            ]
            if existing:
                logger.debug(f"Episode {episode_id} already in database, skipping")
                return existing[0]
        
        try:
            # Extract mission specification from SLAMO format
            source = episode_data.get("source", {})
            target = episode_data.get("target", {})
            trajectory = episode_data.get("trajectory", {})
            outcome = episode_data.get("outcome", {})
            params = episode_data.get("params_snapshot", {})
            safety = episode_data.get("safety", {})
            
            # Create MissionSpec
            mission_spec = MissionSpec(
                start_x=float(source.get("x", 0.0)),
                start_y=float(source.get("y", 0.0)),
                end_x=float(target.get("target_x", 0.0)),
                end_y=float(target.get("target_y", 0.0)),
                estimated_distance=float(trajectory.get("distance_traveled_m", 0.0)),
                obstacle_density=float(source.get("obstacle_density", 0.0)),
            )
            
            # Compute fingerprint
            fingerprint = self.model.compute_fingerprint(mission_spec)
            
            # Compute outcome quality
            efficiency = float(outcome.get("efficiency_score", 0.5))
            safety_score = float(outcome.get("safety_score", 0.5))
            smoothness = float(outcome.get("comfort_jerk_score", 0.5))
            outcome_quality = self.model.compute_outcome_quality(
                efficiency, safety_score, smoothness
            )
            
            # Create entry
            entry = FingerprintEntry(
                episode_id=episode_id,
                location=location,
                fingerprint=fingerprint.tolist(),
                
                # Mission characteristics
                start_x=float(source.get("x", 0.0)),
                start_y=float(source.get("y", 0.0)),
                end_x=float(target.get("target_x", 0.0)),
                end_y=float(target.get("target_y", 0.0)),
                estimated_distance=float(trajectory.get("distance_traveled_m", 0.0)),
                obstacle_density=float(source.get("obstacle_density", 0.0)),
                
                # Quality scores
                efficiency_score=efficiency,
                safety_score=float(outcome.get("safety_score", 0.5)),
                smoothness_score=float(outcome.get("comfort_jerk_score", 0.5)),
                outcome_quality=outcome_quality,
                
                # Outcome
                success_binary=int(outcome.get("success_binary", 0)),
                time_to_goal_s=float(outcome.get("time_to_goal_s", 0.0)),
                composite_score=float(outcome.get("composite_score", 0.0)),
                
                # Parameters
                params_snapshot=params,
                
                # Metadata
                timestamp_ms=int(episode_data.get("start_ts_ms", 0)),
            )
            
            # Add to database
            if location not in self.db.fingerprints_by_location:
                self.db.fingerprints_by_location[location] = []
            
            self.db.fingerprints_by_location[location].append(entry)
            logger.info(
                f"Added fingerprint for {episode_id} "
                f"(quality={outcome_quality:.3f}, location={location})"
            )
            
            return entry
        
        except Exception as e:
            logger.error(f"Failed to add episode {episode_id}: {e}")
            return None
    
    def get_by_location(self, location: str) -> List[FingerprintEntry]:
        """Get all fingerprints for a location."""
        return self.db.fingerprints_by_location.get(location, [])
    
    def get_all(self) -> List[FingerprintEntry]:
        """Get all fingerprints from all locations."""
        result = []
        for entries in self.db.fingerprints_by_location.values():
            result.extend(entries)
        return result
    
    def get_by_episode_id(self, episode_id: str) -> Optional[FingerprintEntry]:
        """Find fingerprint entry by episode ID."""
        for entries in self.db.fingerprints_by_location.values():
            for entry in entries:
                if entry.episode_id == episode_id:
                    return entry
        return None
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        all_entries = self.get_all()
        
        if not all_entries:
            return {
                "total_episodes": 0,
                "locations": 0,
                "quality_avg": 0.0,
                "quality_min": 0.0,
                "quality_max": 0.0,
            }
        
        qualities = [e.outcome_quality for e in all_entries]
        
        return {
            "total_episodes": len(all_entries),
            "locations": len(self.db.fingerprints_by_location),
            "location_counts": {
                loc: len(entries)
                for loc, entries in self.db.fingerprints_by_location.items()
            },
            "quality_avg": sum(qualities) / len(qualities),
            "quality_min": min(qualities),
            "quality_max": max(qualities),
            "success_rate": sum(
                1 for e in all_entries if e.success_binary == 1
            ) / len(all_entries),
        }
