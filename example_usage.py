#!/usr/bin/env python3
"""
example_usage.py: Complete example showing Phase 1 + Phase 2 integration.

Demonstrates:
1. Creating sample episodes
2. Starting the component
3. Sending queries
4. Receiving recommendations
"""

import json
import sys
import time
from pathlib import Path
from threading import Thread

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import EpisodicImproverComponent


def setup_demo_data(component_dir: Path):
    """Create sample episodes for demonstration."""
    print("📁 Setting up demo data...")
    
    episodic_memory_dir = component_dir / "episodic_memory"
    
    # Create location directory
    location_dir = episodic_memory_dir / "demo_location"
    location_dir.mkdir(parents=True, exist_ok=True)
    
    # Sample mission 1: Straight corridor
    episode1 = {
        "mission_spec": {
            "start_x": -20.0,
            "start_y": 0.0,
            "end_x": 20.0,
            "end_y": 0.0,
            "estimated_distance": 40.0,
            "obstacle_density": 0.05,
        },
        "parameters": {
            "goal_tolerance": 0.15,
            "max_velocity": 1.2,
            "max_angular_velocity": 1.2,
            "acceleration": 0.6,
            "angular_acceleration": 0.4,
        },
        "scores": {
            "efficiency": 0.95,
            "safety": 0.90,
            "smoothness": 0.92,
        }
    }
    
    with open(location_dir / "ep_demo_001.json", 'w') as f:
        json.dump(episode1, f, indent=2)
    print("  ✓ Episode 1: Straight corridor (low density)")
    
    # Sample mission 2: Dense obstacles
    episode2 = {
        "mission_spec": {
            "start_x": -15.0,
            "start_y": -10.0,
            "end_x": 15.0,
            "end_y": 10.0,
            "estimated_distance": 45.0,
            "obstacle_density": 0.45,
        },
        "parameters": {
            "goal_tolerance": 0.08,
            "max_velocity": 0.7,
            "max_angular_velocity": 2.0,
            "acceleration": 0.35,
            "angular_acceleration": 0.6,
        },
        "scores": {
            "efficiency": 0.75,
            "safety": 0.85,
            "smoothness": 0.70,
        }
    }
    
    with open(location_dir / "ep_demo_002.json", 'w') as f:
        json.dump(episode2, f, indent=2)
    print("  ✓ Episode 2: Dense obstacles (high safety focus)")
    
    # Sample mission 3: Tight path
    episode3 = {
        "mission_spec": {
            "start_x": 0.0,
            "start_y": -30.0,
            "end_x": 0.0,
            "end_y": 30.0,
            "estimated_distance": 61.0,
            "obstacle_density": 0.30,
        },
        "parameters": {
            "goal_tolerance": 0.10,
            "max_velocity": 0.9,
            "max_angular_velocity": 1.8,
            "acceleration": 0.45,
            "angular_acceleration": 0.5,
        },
        "scores": {
            "efficiency": 0.82,
            "safety": 0.88,
            "smoothness": 0.80,
        }
    }
    
    with open(location_dir / "ep_demo_003.json", 'w') as f:
        json.dump(episode3, f, indent=2)
    print("  ✓ Episode 3: Tight corridor (balanced)")
    
    return location_dir


def run_demo():
    """Run complete demonstration."""
    import tempfile
    
    print("=" * 70)
    print("EPISODIC IMPROVER - COMPLETE DEMONSTRATION")
    print("=" * 70)
    
    # Create temporary component directory
    with tempfile.TemporaryDirectory() as tmpdir:
        component_dir = Path(tmpdir) / "episodic_improver"
        component_dir.mkdir(parents=True, exist_ok=True)
        
        # Create component FIRST
        print("\n🚀 Starting EpisodicImproverComponent...")
        component = EpisodicImproverComponent(
            episodic_memory_dir=component_dir / "episodic_memory",
            etc_dir=component_dir / "etc",
            index_file=component_dir / "etc" / "fingerprint_index.json",
        )
        
        # Run in background
        stop_flag = False
        def run_component():
            nonlocal stop_flag
            component.start()
            while not stop_flag:
                time.sleep(0.5)
            component.stop()
        
        thread = Thread(target=run_component, daemon=True)
        thread.start()
        
        # Wait for startup
        time.sleep(1)
        print("  ✓ Component started and monitoring directories")
        
        # Now setup demo episodes AFTER component is running
        print("\n📁 Creating demo episodes...")
        setup_demo_data(component_dir)
        
        # Wait for episodes to be processed
        time.sleep(2)
        
        # Demo Query 1: Similar to episode 1 (straight)
        print("\n📋 QUERY 1: Straight corridor with obstacles")
        print("   (Similar to Episode 1, should suggest fast/smooth parameters)")
        query1 = {
            "query_id": "demo_query_001",
            "mission_spec": {
                "start_x": -18.0,
                "start_y": 0.0,
                "end_x": 18.0,
                "end_y": 0.0,
                "estimated_distance": 36.0,
                "obstacle_density": 0.08,
            }
        }
        
        query_file1 = component_dir / "etc" / "query_pending.json"
        with open(query_file1, 'w') as f:
            json.dump(query1, f)
        
        # Wait for processing
        time.sleep(2)
        
        # Check recommendations for query 1
        reco_file1 = component_dir / "etc" / "recommendations" / "recommendations_demo_query_001.json"
        if reco_file1.exists():
            with open(reco_file1, 'r') as f:
                reco1 = json.load(f)
            
            print(f"\n✅ Recommendations for Query 1:")
            print(f"   Status: {reco1['status']}")
            print(f"   Found {len(reco1['recommendations'])} similar episodes")
            print(f"   Mean Similarity: {reco1['statistics']['mean_similarity']:.4f}")
            
            if reco1['recommendations']:
                top = reco1['recommendations'][0]
                print(f"\n   🏆 Top Recommendation:")
                print(f"      Source Episode: {top['source_episode_id']}")
                print(f"      Similarity: {top['similarity']:.4f}")
                print(f"      Perturbation: {top['perturbation_info']['strategy']} "
                      f"(σ={top['perturbation_info']['sigma_pct']:.1f}%)")
                print(f"      Recommended max_velocity: {top['recommended_parameters']['max_velocity']:.2f} m/s")
                print(f"      Recommended goal_tolerance: {top['recommended_parameters']['goal_tolerance']:.3f} m")
        
        # Demo Query 2: Dense obstacles (tight space)
        print("\n\n📋 QUERY 2: Dense obstacles path")
        print("   (Similar to Episode 2, should suggest careful/safe parameters)")
        query2 = {
            "query_id": "demo_query_002",
            "mission_spec": {
                "start_x": -12.0,
                "start_y": -8.0,
                "end_x": 12.0,
                "end_y": 8.0,
                "estimated_distance": 42.0,
                "obstacle_density": 0.50,
            }
        }
        
        query_file2 = component_dir / "etc" / "query_pending.json"
        with open(query_file2, 'w') as f:
            json.dump(query2, f)
        
        # Wait for processing
        time.sleep(2)
        
        # Check recommendations for query 2
        reco_file2 = component_dir / "etc" / "recommendations" / "recommendations_demo_query_002.json"
        if reco_file2.exists():
            with open(reco_file2, 'r') as f:
                reco2 = json.load(f)
            
            print(f"\n✅ Recommendations for Query 2:")
            print(f"   Status: {reco2['status']}")
            print(f"   Found {len(reco2['recommendations'])} similar episodes")
            
            if reco2['recommendations']:
                top = reco2['recommendations'][0]
                print(f"\n   🏆 Top Recommendation:")
                print(f"      Source Episode: {top['source_episode_id']}")
                print(f"      Similarity: {top['similarity']:.4f}")
                print(f"      Perturbation: {top['perturbation_info']['strategy']}")
                print(f"      Recommended max_velocity: {top['recommended_parameters']['max_velocity']:.2f} m/s")
                print(f"      Recommended goal_tolerance: {top['recommended_parameters']['goal_tolerance']:.3f} m")
        
        # Summary
        print("\n" + "=" * 70)
        print("DEMONSTRATION COMPLETE")
        print("=" * 70)
        print(f"\n📊 Final Index State:")
        print(f"   Episodes in memory: {component.engine.get_episode_count()}")
        print(f"   Queries processed: 2")
        print(f"   Recommendations generated: {len(reco1.get('recommendations', [])) + len(reco2.get('recommendations', []))}")
        
        # Shutdown
        stop_flag = True
        thread.join(timeout=5)
        print("\n✓ Component shutdown gracefully")


if __name__ == "__main__":
    run_demo()
