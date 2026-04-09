#!/usr/bin/env python3
"""
test_integration.py: Integration test for Phase 2 components.

Tests:
1. Directory monitoring (detects new episodes and queries)
2. Recommendation generation
3. Output file creation
"""

import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from threading import Thread

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

from src.main import EpisodicImproverComponent


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_integration():
    """Run integration test."""
    
    # Create temporary directories
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        episodic_memory_dir = tmpdir / "episodic_memory"
        etc_dir = tmpdir / "etc"
        index_file = etc_dir / "fingerprint_index.json"
        recommendations_dir = etc_dir / "recommendations"
        
        logger.info("="*70)
        logger.info("PHASE 2 INTEGRATION TEST")
        logger.info("="*70)
        
        # Create component
        logger.info("Creating component...")
        component = EpisodicImproverComponent(
            episodic_memory_dir=episodic_memory_dir,
            etc_dir=etc_dir,
            index_file=index_file,
        )
        
        # Start component in background
        logger.info("Starting component...")
        stop_flag = False
        
        def run_component():
            nonlocal stop_flag
            component.start()
            while not stop_flag:
                time.sleep(0.5)
            component.stop()
        
        component_thread = Thread(target=run_component, daemon=True)
        component_thread.start()
        
        # Give component time to start
        time.sleep(1)
        
        # Test 1: Add sample episodes to episodic_memory
        logger.info("\n[TEST 1] Creating sample episodes...")
        location_dir = episodic_memory_dir / "test_location"
        location_dir.mkdir(parents=True, exist_ok=True)
        
        episode_data = {
            "mission_spec": {
                "start_x": 0.0,
                "start_y": -27.0,
                "end_x": 0.0,
                "end_y": 26.8,
                "estimated_distance": 54.0,
                "obstacle_density": 0.12,
            },
            "parameters": {
                "goal_tolerance": 0.10,
                "max_velocity": 1.0,
                "max_angular_velocity": 1.5,
                "acceleration": 0.5,
                "angular_acceleration": 0.3,
            },
            "scores": {
                "efficiency": 0.90,
                "safety": 0.80,
                "smoothness": 0.85,
            }
        }
        
        episode_file = location_dir / "ep_test_001.json"
        with open(episode_file, 'w') as f:
            json.dump(episode_data, f)
        
        logger.info(f"✓ Created episode: {episode_file.name}")
        
        # Wait for component to process
        time.sleep(2)
        
        # Test 2: Create query
        logger.info("\n[TEST 2] Creating query...")
        query_data = {
            "query_id": "query_test_001",
            "mission_spec": {
                "start_x": 0.0,
                "start_y": -27.0,
                "end_x": 0.0,
                "end_y": 26.8,
                "estimated_distance": 54.0,
                "obstacle_density": 0.11,
            },
        }
        
        query_file = etc_dir / "query_pending.json"
        with open(query_file, 'w') as f:
            json.dump(query_data, f)
        
        logger.info(f"✓ Created query: {query_file.name}")
        
        # Wait for component to process
        time.sleep(2)
        
        # Test 3: Check that recommendation was generated
        logger.info("\n[TEST 3] Checking recommendation output...")
        recommendations_dir.mkdir(parents=True, exist_ok=True)
        
        reco_file = recommendations_dir / "recommendations_query_test_001.json"
        if reco_file.exists():
            with open(reco_file, 'r') as f:
                reco_data = json.load(f)
            
            logger.info(f"✓ Recommendation file created: {reco_file.name}")
            logger.info(f"  - Status: {reco_data.get('status')}")
            logger.info(f"  - Recommendations: {len(reco_data.get('recommendations', []))}")
            
            if reco_data.get('recommendations'):
                first_reco = reco_data['recommendations'][0]
                logger.info(f"  - Top recommendation:")
                logger.info(f"    - Source: {first_reco.get('source_episode_id')}")
                logger.info(f"    - Similarity: {first_reco.get('similarity'):.4f}")
                logger.info(f"    - Strategy: {first_reco.get('perturbation_info', {}).get('strategy')}")
        else:
            logger.error(f"✗ Recommendation file NOT found: {reco_file}")
        
        # Test 4: Check that query was removed
        logger.info("\n[TEST 4] Checking query cleanup...")
        if query_file.exists():
            logger.error(f"✗ Query file still exists (should have been removed)")
        else:
            logger.info(f"✓ Query file was removed after processing")
        
        # Test 5: Check index was saved
        logger.info("\n[TEST 5] Checking index persistence...")
        stop_flag = True
        component_thread.join(timeout=5)
        
        if index_file.exists():
            with open(index_file, 'r') as f:
                index_data = json.load(f)
            logger.info(f"✓ Index file saved: {index_file.name}")
            logger.info(f"  - Episodes in index: {len(index_data.get('episodes', []))}")
        else:
            logger.error(f"✗ Index file NOT saved")
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("INTEGRATION TEST COMPLETED")
        logger.info("="*70)


if __name__ == "__main__":
    test_integration()
