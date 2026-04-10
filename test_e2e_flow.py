#!/usr/bin/env python3
"""
Test END-TO-END del flujo PRE-MISIÓN: 
SLAMO escriba mission_initial → episodic_improver genera predictions → SLAMO lee y aplica
"""

import json
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EPISODIC_MEMORY_DIR = Path("/home/varo/robocomp/components/episodic_improver/episodic_memory")

def test_end_to_end_flow():
    """Simula el flujo completo de PRE-MISIÓN"""
    
    logger.info("\n" + "="*70)
    logger.info("TEST END-TO-END: SLAMO ↔ episodic_improver PRE-MISIÓN")
    logger.info("="*70)
    
    # Step 1: SLAMO escribe mission_initial
    logger.info("\n[STEP 1] SLAMO escriba mission_initial_*.json")
    mission_id = f"e2e_test_{int(time.time())}"
    mission_file = EPISODIC_MEMORY_DIR / f"mission_initial_{mission_id}.json"
    
    mission_data = {
        "mission_id": mission_id,
        "source_x": 0.0,
        "source_y": 0.0,
        "target_x": 5.0,
        "target_y": 5.0,
        "estimated_distance": 7.07,
        "obstacle_density": 0.05
    }
    
    with open(mission_file, 'w') as f:
        json.dump(mission_data, f, indent=2)
    logger.info(f"  ✓ Written: {mission_file.name}")
    logger.info(f"    Mission: ({mission_data['source_x']}, {mission_data['source_y']}) → ({mission_data['target_x']}, {mission_data['target_y']})")
    
    # Step 2: Esperar a que episodic_improver genere predictions
    logger.info("\n[STEP 2] episodic_improver detecta y genera predictions_*.json")
    predictions_file = EPISODIC_MEMORY_DIR / f"predictions_{mission_id}.json"
    
    timeout = 5
    start_time = time.time()
    while not predictions_file.exists() and (time.time() - start_time) < timeout:
        time.sleep(0.1)
    
    if predictions_file.exists():
        logger.info(f"  ✓ Generated: {predictions_file.name}")
        
        # Leer las predicciones
        with open(predictions_file, 'r') as f:
            predictions = json.load(f)
        
        logger.info(f"    Status: {predictions.get('status')}")
        logger.info(f"    Best match: {predictions.get('best_match_id')}")
        logger.info(f"    Similarity: {predictions.get('best_match_similarity'):.1%}")
        
        # Step 3: SLAMO lee y aplica los parámetros
        logger.info("\n[STEP 3] SLAMO lee predictions y aplica parámetros")
        params = predictions.get('predicted_parameters', {})
        
        if predictions.get('status') in ['ready', 'success']:
            logger.info("  ✓ Status válido para aplicar predicciones")
            logger.info("  Parameters aplicables:")
            for key, value in params.items():
                logger.info(f"    - {key}: {value}")
            
            logger.info("\n  [En SLAMO real:]")
            logger.info("    trajectory_controller.params.mood = " + str(params.get('base_speed', 'N/A')))
            logger.info("    trajectory_controller.params.max_adv = " + str(params.get('max_adv_speed', 'N/A')))
            logger.info("    trajectory_controller.params.max_rot = " + str(params.get('angular_velocity', 'N/A')))
        else:
            logger.error(f"  ✗ Status inválido: {predictions.get('status')}")
            return False
        
        # Step 4: SLAMO completa la misión y guarda outcome
        logger.info("\n[STEP 4] SLAMO termina misión y guarda mission_outcome_*.json")
        outcome_file = EPISODIC_MEMORY_DIR / f"mission_outcome_{mission_id}.json"
        
        outcome_data = {
            "mission_id": mission_id,
            "status": "success",
            "duration_s": 12.5,
            "success": 1,
            "distance_traveled_m": 7.15,
            "path_efficiency": 0.99,
            "min_esdf_m": 0.45,
            "mean_speed": 0.57
        }
        
        with open(outcome_file, 'w') as f:
            json.dump(outcome_data, f, indent=2)
        logger.info(f"  ✓ Written: {outcome_file.name}")
        logger.info(f"    Success: {bool(outcome_data['success'])}, Duration: {outcome_data['duration_s']}s")
        
        # Summary
        logger.info("\n" + "="*70)
        logger.info("✓ FLUJO COMPLETO EXITOSO")
        logger.info("="*70)
        logger.info("Archivos generados:")
        logger.info(f"  1. {mission_file.name} - Input de SLAMO")
        logger.info(f"  2. {predictions_file.name} - Output de episodic_improver")
        logger.info(f"  3. {outcome_file.name} - Outcome de SLAMO")
        logger.info("\nLas nuevas misiones ahora se guardan en 3 contextos:")
        logger.info("  • episodic_memory/{episode_id}.json (episodio completo de SLAMO - existía)")
        logger.info("  • mission_initial_{episode_id}.json (para PRE-MISIÓN - NUEVO)")
        logger.info("  • mission_outcome_{episode_id}.json (resultado para episódic_improver - NUEVO)")
        logger.info("="*70 + "\n")
        
        return True
    else:
        logger.error(f"  ✗ Timeout esperando: {predictions_file.name}")
        return False

if __name__ == "__main__":
    success = test_end_to_end_flow()
    exit(0 if success else 1)
