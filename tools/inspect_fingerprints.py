#!/usr/bin/env python3
"""
inspect_fingerprints.py: Browse and inspect fingerprint database.

Provides tools to visualize fingerprint data, search, filter, and analyze
episodes in the database.
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fingerprint_database import FingerprintDatabaseManager, FingerprintEntry


def print_header(text: str, width: int = 80) -> None:
    """Print formatted header."""
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def print_fingerprint_entry(entry: FingerprintEntry, verbose: bool = False) -> None:
    """
    Print a formatted fingerprint entry.
    
    Args:
        entry: FingerprintEntry to print.
        verbose: If True, show all details including params.
    """
    print(f"\nEpisode ID: {entry.episode_id}")
    print(f"Location:   {entry.location}")
    
    # Mission info
    print(f"\nMission:")
    print(f"  Start:          ({entry.start_x:7.2f}, {entry.start_y:7.2f})")
    print(f"  End:            ({entry.end_x:7.2f}, {entry.end_y:7.2f})")
    print(f"  Distance:       {entry.estimated_distance:7.2f} m")
    print(f"  Density:        {entry.obstacle_density:7.3f}")
    
    # Fingerprint
    print(f"\nFingerprint (9D):")
    fp_labels = ["start_x", "start_y", "end_x", "end_y", "heading", "dist", "tort", "density", "hardness"]
    for i, (label, value) in enumerate(zip(fp_labels, entry.fingerprint)):
        print(f"  {label:12s}: {value:8.4f}")
    
    # Quality scores
    print(f"\nQuality Scores:")
    print(f"  Efficiency:     {entry.efficiency_score:7.3f}")
    print(f"  Safety:         {entry.safety_score:7.3f}")
    print(f"  Smoothness:     {entry.smoothness_score:7.3f}")
    print(f"  Outcome:        {entry.outcome_quality:7.3f}")
    
    # Outcome
    print(f"\nOutcome:")
    print(f"  Success:        {'✓ Yes' if entry.success_binary else '✗ No'}")
    print(f"  Time to goal:   {entry.time_to_goal_s:7.2f} s")
    print(f"  Composite:      {entry.composite_score:7.2f}")
    
    # Verbose: Parameters
    if verbose and entry.params_snapshot:
        print(f"\nParameters ({len(entry.params_snapshot)} params):")
        for param, value in sorted(entry.params_snapshot.items())[:10]:
            print(f"  {param:30s}: {value}")
        if len(entry.params_snapshot) > 10:
            print(f"  ... and {len(entry.params_snapshot) - 10} more")


def cmd_list(database_manager: FingerprintDatabaseManager, args) -> int:
    """List episodes in database."""
    location = args.location
    limit = args.limit
    
    db_manager = database_manager
    
    if location:
        entries = db_manager.get_by_location(location)
        print_header(f"Episodes in '{location}' ({len(entries)} total)")
    else:
        entries = db_manager.get_all()
        print_header(f"All Episodes in Database ({len(entries)} total)")
    
    # Sort by quality descending
    entries_sorted = sorted(entries, key=lambda e: e.outcome_quality, reverse=True)
    
    # Print table header
    print(f"\n{'#':<4} {'Episode ID':<30} {'Loc':<20} {'Quality':<8} {'Success':<7} {'Distance':<10}")
    print("-" * 80)
    
    # Print entries
    for i, entry in enumerate(entries_sorted[:limit], 1):
        success = "✓" if entry.success_binary else "✗"
        print(
            f"{i:<4} {entry.episode_id:<30} {entry.location:<20} "
            f"{entry.outcome_quality:<8.3f} {success:<7} {entry.estimated_distance:<10.2f}"
        )
    
    if len(entries_sorted) > limit:
        print(f"\n... and {len(entries_sorted) - limit} more episodes (use --limit to see more)")
    
    return 0


def cmd_show(database_manager: FingerprintDatabaseManager, args) -> int:
    """Show details of a specific episode."""
    entry = database_manager.get_by_episode_id(args.episode_id)
    
    if not entry:
        print(f"✗ Episode not found: {args.episode_id}")
        return 1
    
    print_header(f"Episode Details: {args.episode_id}")
    print_fingerprint_entry(entry, verbose=args.verbose)
    
    return 0


def cmd_stats(database_manager: FingerprintDatabaseManager, args) -> int:
    """Show database statistics."""
    stats = database_manager.get_stats()
    
    print_header("Database Statistics")
    
    print(f"\nOverall:")
    print(f"  Total episodes:    {stats['total_episodes']}")
    print(f"  Locations:         {stats['locations']}")
    
    print(f"\nQuality Metrics:")
    print(f"  Average quality:   {stats['quality_avg']:.3f}")
    print(f"  Min quality:       {stats['quality_min']:.3f}")
    print(f"  Max quality:       {stats['quality_max']:.3f}")
    print(f"  Success rate:      {stats['success_rate']:.1%}")
    
    print(f"\nEpisodes per Location:")
    for location, count in sorted(
        stats['location_counts'].items(),
        key=lambda x: x[1],
        reverse=True
    ):
        bar = "█" * (count // 2)
        print(f"  {location:25s}: {count:3d} {bar}")
    
    print("\n")
    return 0


def cmd_search(database_manager: FingerprintDatabaseManager, args) -> int:
    """Search for episodes by location or quality threshold."""
    entries = database_manager.get_all()
    
    if args.location:
        entries = [e for e in entries if e.location == args.location]
    
    if args.quality:
        entries = [e for e in entries if e.outcome_quality >= args.quality]
    
    # Sort by quality descending
    entries = sorted(entries, key=lambda e: e.outcome_quality, reverse=True)
    
    print_header(f"Search Results ({len(entries)} episodes found)")
    
    # Print table header
    print(f"\n{'#':<4} {'Episode ID':<30} {'Location':<20} {'Quality':<8}")
    print("-" * 65)
    
    # Print entries
    for i, entry in enumerate(entries[:args.limit], 1):
        print(
            f"{i:<4} {entry.episode_id:<30} {entry.location:<20} "
            f"{entry.outcome_quality:<8.3f}"
        )
    
    if len(entries) > args.limit:
        print(f"\n... and {len(entries) - args.limit} more episodes")
    
    return 0


def cmd_export(database_manager: FingerprintDatabaseManager, args) -> int:
    """Export database to CSV."""
    entries = database_manager.get_all()
    
    output_file = Path(args.output)
    
    try:
        with open(output_file, "w") as f:
            # Header
            f.write(
                "episode_id,location,quality,efficiency,safety,smoothness,"
                "success,distance,time_to_goal,start_x,start_y,end_x,end_y,"
                "obstacle_density\n"
            )
            
            # Rows
            for entry in entries:
                f.write(
                    f"{entry.episode_id},{entry.location},"
                    f"{entry.outcome_quality:.3f},{entry.efficiency_score:.3f},"
                    f"{entry.safety_score:.3f},{entry.smoothness_score:.3f},"
                    f"{entry.success_binary},{entry.estimated_distance:.2f},"
                    f"{entry.time_to_goal_s:.2f},"
                    f"{entry.start_x:.3f},{entry.start_y:.3f},"
                    f"{entry.end_x:.3f},{entry.end_y:.3f},"
                    f"{entry.obstacle_density:.3f}\n"
                )
        
        print(f"✓ Exported {len(entries)} episodes to {output_file}")
        return 0
    
    except Exception as e:
        print(f"✗ Failed to export: {e}")
        return 1


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Browse and inspect fingerprint database"
    )
    
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("etc/fingerprint_database.json"),
        help="Path to database file (default: etc/fingerprint_database.json)",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List episodes")
    list_parser.add_argument(
        "--location",
        type=str,
        help="Filter by location",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max episodes to show (default: 20)",
    )
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show episode details")
    show_parser.add_argument("episode_id", help="Episode ID to show")
    show_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all details including parameters",
    )
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search episodes")
    search_parser.add_argument(
        "--location",
        type=str,
        help="Filter by location",
    )
    search_parser.add_argument(
        "--quality",
        type=float,
        help="Minimum quality score",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max episodes to show (default: 20)",
    )
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export to CSV")
    export_parser.add_argument(
        "--output",
        type=Path,
        default=Path("fingerprints_export.csv"),
        help="Output CSV file (default: fingerprints_export.csv)",
    )
    
    args = parser.parse_args()
    
    # Load database
    db_manager = FingerprintDatabaseManager(database_file=args.database)
    
    # Dispatch commands
    if args.command == "list":
        return cmd_list(db_manager, args)
    elif args.command == "show":
        return cmd_show(db_manager, args)
    elif args.command == "stats":
        return cmd_stats(db_manager, args)
    elif args.command == "search":
        return cmd_search(db_manager, args)
    elif args.command == "export":
        return cmd_export(db_manager, args)
    else:
        parser.print_help()
        # Show default: stats
        print("\n(Showing default: database statistics)")
        return cmd_stats(db_manager, args)


if __name__ == "__main__":
    sys.exit(main())
