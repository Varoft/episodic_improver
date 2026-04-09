#!/usr/bin/env python3
"""
add_fingerprints.py: Add fingerprint entries to the database.

Offers two modes:
1. Batch: Scan all episodes in a directory and add them to database
2. Single: Add a single episode to database
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fingerprint_database import FingerprintDatabaseManager
from episodic_improver import FingerprintModel


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_location_from_path(episode_path: Path) -> Optional[str]:
    """
    Extract location name from episode path.
    
    Expected structure: episodic_memory/{location}/ep_*.json
    """
    try:
        # Check if parent directory looks like a location
        parent = episode_path.parent.name
        episodic_parent = episode_path.parent.parent.name
        
        if episodic_parent == "episodic_memory":
            return parent
        return None
    except:
        return None


def add_single_episode(
    episode_path: Path,
    database_file: Path = Path("etc/fingerprint_database.json"),
) -> bool:
    """
    Add a single episode to the database.
    
    Args:
        episode_path: Path to episode JSON file.
        database_file: Path to fingerprint database file.
    
    Returns:
        True if successful, False otherwise.
    """
    # Verify file exists
    if not episode_path.exists():
        logger.error(f"Episode file not found: {episode_path}")
        return False
    
    # Extract location
    location = extract_location_from_path(episode_path)
    if not location:
        logger.error(f"Could not extract location from path: {episode_path}")
        return False
    
    # Load episode data
    try:
        with open(episode_path, "r") as f:
            episode_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load episode {episode_path}: {e}")
        return False
    
    # Get episode ID from filename
    episode_id = episode_path.stem
    
    # Initialize database manager
    db_manager = FingerprintDatabaseManager(
        database_file=database_file,
        fingerprint_model=FingerprintModel(),
    )
    
    # Add episode
    entry = db_manager.add_episode(
        episode_id=episode_id,
        location=location,
        episode_data=episode_data,
    )
    
    if entry:
        # Save database
        db_manager.save()
        logger.info(f"✓ Successfully added {episode_id} to {database_file}")
        return True
    else:
        logger.error(f"✗ Failed to add {episode_id}")
        return False


def batch_add_episodes(
    episodic_memory_dir: Path = Path("episodic_memory"),
    database_file: Path = Path("etc/fingerprint_database.json"),
    skip_existing: bool = True,
) -> bool:
    """
    Scan episodic_memory directory and add all episodes to database.
    
    Args:
        episodic_memory_dir: Root episodic memory directory.
        database_file: Path to fingerprint database file.
        skip_existing: Skip episodes already in database.
    
    Returns:
        True if successful, False if any failures.
    """
    # Verify directory exists
    if not episodic_memory_dir.exists():
        logger.error(f"Directory not found: {episodic_memory_dir}")
        return False
    
    # Initialize database manager
    db_manager = FingerprintDatabaseManager(
        database_file=database_file,
        fingerprint_model=FingerprintModel(),
    )
    
    # Scan for episodes
    episode_files = sorted(episodic_memory_dir.glob("**/ep_*.json"))
    
    if not episode_files:
        logger.warning(f"No episodes found in {episodic_memory_dir}")
        return True
    
    logger.info(f"Found {len(episode_files)} episodes to process")
    
    # Process each episode
    added = 0
    skipped = 0
    failed = 0
    
    for episode_path in episode_files:
        episode_id = episode_path.stem
        location = extract_location_from_path(episode_path)
        
        if not location:
            logger.warning(f"Skipping {episode_path} (unknown location)")
            skipped += 1
            continue
        
        # Skip if already exists
        if skip_existing and db_manager.get_by_episode_id(episode_id):
            logger.debug(f"Skipping {episode_id} (already in database)")
            skipped += 1
            continue
        
        # Load and add
        try:
            with open(episode_path, "r") as f:
                episode_data = json.load(f)
            
            entry = db_manager.add_episode(
                episode_id=episode_id,
                location=location,
                episode_data=episode_data,
            )
            
            if entry:
                added += 1
            else:
                failed += 1
        
        except Exception as e:
            logger.error(f"Failed to process {episode_path}: {e}")
            failed += 1
    
    # Save database once at the end
    if added > 0:
        db_manager.save()
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Batch Add Summary")
    logger.info("=" * 60)
    logger.info(f"Total episodes:    {len(episode_files)}")
    logger.info(f"Added:             {added}")
    logger.info(f"Skipped:           {skipped}")
    logger.info(f"Failed:            {failed}")
    
    # Print stats
    stats = db_manager.get_stats()
    logger.info("=" * 60)
    logger.info("Database Statistics")
    logger.info("=" * 60)
    logger.info(f"Total in database: {stats['total_episodes']}")
    logger.info(f"Locations:         {stats['locations']}")
    logger.info(f"Location counts:   {stats['location_counts']}")
    logger.info(f"Avg quality:       {stats['quality_avg']:.3f}")
    logger.info(f"Quality range:     [{stats['quality_min']:.3f}, {stats['quality_max']:.3f}]")
    logger.info(f"Success rate:      {stats['success_rate']:.1%}")
    logger.info("=" * 60)
    
    return failed == 0


def main():
    """Main entry point with CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Add fingerprint entries to database"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch add all episodes")
    batch_parser.add_argument(
        "--episodic-memory",
        type=Path,
        default=Path("episodic_memory"),
        help="Path to episodic_memory directory (default: episodic_memory)",
    )
    batch_parser.add_argument(
        "--database",
        type=Path,
        default=Path("etc/fingerprint_database.json"),
        help="Path to database file (default: etc/fingerprint_database.json)",
    )
    batch_parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Don't skip existing episodes",
    )
    
    # Single command
    single_parser = subparsers.add_parser("single", help="Add single episode")
    single_parser.add_argument(
        "episode_path",
        type=Path,
        help="Path to episode JSON file",
    )
    single_parser.add_argument(
        "--database",
        type=Path,
        default=Path("etc/fingerprint_database.json"),
        help="Path to database file (default: etc/fingerprint_database.json)",
    )
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show database info")
    info_parser.add_argument(
        "--database",
        type=Path,
        default=Path("etc/fingerprint_database.json"),
        help="Path to database file (default: etc/fingerprint_database.json)",
    )
    
    args = parser.parse_args()
    
    if args.command == "batch":
        success = batch_add_episodes(
            episodic_memory_dir=args.episodic_memory,
            database_file=args.database,
            skip_existing=not args.no_skip_existing,
        )
        return 0 if success else 1
    
    elif args.command == "single":
        success = add_single_episode(
            episode_path=args.episode_path,
            database_file=args.database,
        )
        return 0 if success else 1
    
    elif args.command == "info":
        db_manager = FingerprintDatabaseManager(database_file=args.database)
        stats = db_manager.get_stats()
        
        print("\n" + "=" * 60)
        print("Fingerprint Database Information")
        print("=" * 60)
        print(f"Database file:     {args.database}")
        print(f"Total episodes:    {stats['total_episodes']}")
        print(f"Locations:         {stats['locations']}")
        
        if stats['location_counts']:
            print("\nEpisodes per location:")
            for loc, count in stats['location_counts'].items():
                print(f"  {loc:25s}: {count:3d}")
        
        if stats['total_episodes'] > 0:
            print(f"\nQuality statistics:")
            print(f"  Average:         {stats['quality_avg']:.3f}")
            print(f"  Min:             {stats['quality_min']:.3f}")
            print(f"  Max:             {stats['quality_max']:.3f}")
            print(f"  Success rate:    {stats['success_rate']:.1%}")
        
        print("=" * 60 + "\n")
    
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
