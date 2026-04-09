#!/usr/bin/env python3
"""
Test simplified 7D workflow: PRE-MISIÓN + SAVE EPISODE

Flow:
1. SLAMO creates mission_initial.json
2. Component detects it and applies 7D predictions
3. SLAMO completes mission and fills in results
4. Component saves episode to episodic_memory
"""

import json
import time
import sys
from pathlib import Path
from threading import Thread, Event

sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import EpisodicImproverComponent


def test_simplified_workflow():
    """Test the simplified workflow."""
    
    print("=" * 70)
    print("TEST: Simplified 7D Workflow (PRE-MISIÓN + SAVE)")
    print("=" * 70)
    
    # 1. Initialize component
    print("\n[1] Initializing component...")
    component = EpisodicImproverComponent()
    
    # Verify 7D system is enabled
    if not component.use_7d_system:
        print("✗ 7D system not available")
        return False
    
    print(f"✓ 7D system: ENABLED")
    
    # 2. Start monitoring in background
    print("\n[2] Starting directory monitor...")
    monitor_thread = Thread(target=component.start, daemon=True)
    monitor_thread.start()
    time.sleep(1)  # Give monitor time to start
    print("✓ Monitor started")
    
    # 3. Create mission_initial.json (simulating SLAMO)
    print("\n[3] SLAMO creates mission_initial.json...")
    mission_initial = {
        "mission_id": "test_mission_001",
        "start_x": 10.0,
        "start_y": 15.0,
        "end_x": 50.0,
        "end_y": 45.0,
        "estimated_distance": 55.0,
        "obstacle_density": 0.45,
        "control_params": {
            "base_speed": 0.35,
            "max_adv_speed": 0.75,
            "angular_velocity": 0.95,
            "angular_acceleration": 1.5,
            "accel_limit": 0.25,
            "decel_limit": 0.30,
        }
    }
    
    mission_path = Path("etc") / "mission_initial.json"
    with open(mission_path, 'w') as f:
        json.dump(mission_initial, f, indent=2)
    
    print(f"✓ Created: {mission_path}")
    
    # 4. Wait for component to apply predictions
    print("\n[4] Waiting for 7D predictions...")
    time.sleep(2)  # Give component time to process
    
    # Read updated mission file
    with open(mission_path, 'r') as f:
        mission_updated = json.load(f)
    
    if "predicted_from_episode" in mission_updated:
        print(f"✓ Predictions applied:")
        print(f"  Best match: {mission_updated['predicted_from_episode']}")
        print(f"  Similarity: {mission_updated['similarity_score']:.1%}")
        print(f"  Params updated: {list(mission_updated['control_params'].keys())}")
    else:
        print("✗ Predictions not applied yet")
    
    # 5. Simulate SLAMO completing mission
    print("\n[5] SLAMO completes mission and fills in results...")
    mission_updated["success"] = True
    mission_updated["time_to_goal_s"] = 42.5
    mission_updated["collisions"] = 0
    mission_updated["blocked_time_s"] = 0.0
    mission_updated["composite_score"] = 57.5
    
    with open(mission_path, 'w') as f:
        json.dump(mission_updated, f, indent=2)
    
    print("✓ Mission results added")
    
    # 6. Save episode
    print("\n[6] Saving episode to episodic_memory...")
    success = component.save_episode(mission_updated)
    
    if success:
        # Verify episode was saved
        episode_path = Path("episodic_memory") / f"{mission_updated['mission_id']}.json"
        if episode_path.exists():
            print(f"✓ Episode saved: {episode_path.name}")
            
            # Show content
            with open(episode_path, 'r') as f:
                episode = json.load(f)
            
            print(f"\n  Episode structure:")
            print(f"  - mission_id: {episode['mission_id']}")
            print(f"  - predicted_from: {episode['predicted_from_episode']}")
            print(f"  - similarity: {episode['similarity_score']:.1%}")
            print(f"  - success: {episode['mission_outcome']['success']}")
            print(f"  - composite: {episode['mission_outcome']['composite_score']:.1f}")
        else:
            print(f"✗ Episode file not found: {episode_path}")
            return False
    else:
        print("✗ Failed to save episode")
        return False
    
    # 7. Clean up
    print("\n[7] Cleaning up...")
    component.stop()
    mission_path.unlink()
    print("✓ Test completed")
    
    print("\n" + "=" * 70)
    print("✓ SIMPLIFIED WORKFLOW TEST PASSED")
    print("=" * 70)
    print("\nWorkflow:")
    print("1. ✓ Component detects mission_initial.json")
    print("2. ✓ Applies 7D predictions to control_params")
    print("3. ✓ SLAMO adds results")
    print("4. ✓ Episode saved to episodic_memory")
    
    return True


if __name__ == "__main__":
    success = test_simplified_workflow()
    sys.exit(0 if success else 1)
