"""
EpisodicImprover7D: Orquestador central del sistema
Integra: extracción 7D → búsqueda K-NN → perturbación → ejecución → evaluación
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json

from index_7d_manager import Index7DManager
from fingerprint_extractor import FingerprintExtractor
from parameter_perturbation import ParameterPerturbation
from mission_evaluator import MissionEvaluator


class EpisodicImprover7D:
    """
    Orquestador del sistema 7D end-to-end.
    
    Flujo completo:
    1. [PRE-MISIÓN] Detectar misión → extraer FP 7D → buscar K-NN → perturbar params
    2. [EJECUCIÓN] Lanzar misión con parámetros perturbados
    3. [POST-MISIÓN] Comparar outcome vs best-match → registrar aprendizaje
    """
    
    def __init__(
        self,
        index_path: str,
        learning_log_path: str = "./episodic_memory/learning_log.json",
        index_weights: Optional[List[float]] = None
    ):
        """
        Inicializa el sistema 7D.
        
        Args:
            index_path: Ruta al fingerprints_index_unified_7d.json
            learning_log_path: Ruta al archivo de log de aprendizaje
            index_weights: Pesos para la métrica de distancia [w1, ..., w7]
        """
        print("=" * 70)
        print("INICIALIZANDO EpisodicImprover7D")
        print("=" * 70)
        
        # Componentes
        self.index_manager = Index7DManager(index_path, weights=index_weights)
        self.fingerprint_extractor = FingerprintExtractor()
        self.parameter_perturbator = ParameterPerturbation()
        self.mission_evaluator = MissionEvaluator(learning_log_path)
        
        # Estado de la última operación
        self.last_query_fp = None
        self.last_search_results = None
        self.last_best_match = None
        self.last_perturbed_params = None
        self.last_perturbed_param_name = None
    
    def pre_mission_prediction(
        self,
        src_x: float,
        src_y: float,
        target_x: float,
        target_y: float,
        obstacle_density: float,
        estimated_distance: float
    ) -> Dict:
        """
        [FASE PRE-MISIÓN] Predice parámetros optimizados antes de lanzar.
        
        Pasos:
        1. Extraer fingerprint 7D
        2. Normalizar
        3. Buscar top-3 episodios similares
        4. Seleccionar best-match
        5. Perturbar parámetros
        
        Args:
            src_x, src_y: Posición del robot
            target_x, target_y: Destino
            obstacle_density: Densidad de obstáculos [0, 1]
            estimated_distance: Distancia estimada del camino
            
        Returns:
            Dict con predicción:
            {
                'status': 'ready',
                'fingerprint_7d': [...],
                'best_match_id': 'ep_xxx',
                'best_match_similarity': 0.XX,
                'predicted_params': {...},
                'perturbation': {'param': 'xxx', 'sigma': X.XX},
                'search_results': [top-3]
            }
        """
        
        print("\n" + "-" * 70)
        print("[PRE-MISIÓN] Predicción de parámetros")
        print("-" * 70)
        
        try:
            # 1. Extraer fingerprint 7D
            fp_raw = self.fingerprint_extractor.extract_7d(
                src_x, src_y, target_x, target_y, obstacle_density, estimated_distance
            )
            self.last_query_fp = fp_raw
            
            print(f"▶ Fingerprint 7D extraído:")
            print(f"  {self.fingerprint_extractor.describe_fingerprint(fp_raw)}")
            
            # 2. Buscar K-NN (top-3)
            search_results = self.index_manager.search_knn(fp_raw, k=3)
            self.last_search_results = search_results
            
            print(f"\n▶ Búsqueda K-NN:")
            for result in search_results:
                print(f"  [{result['rank']}] {result['episode_id']}")
                print(f"      Similitud: {result['similarity_score']:.1%}")
            
            # 3. Seleccionar best-match (primero en la búsqueda)
            best_match = search_results[0]
            self.last_best_match = best_match
            
            # Obtener parámetros del histórico (estos están parcialmente en el índice)
            # Para esta prueba, usaremos parámetros de ejemplo
            # En producción, se cargarían desde los archivos JSON individuales
            best_match_params = {
                'base_speed': 0.35,
                'max_adv_speed': 0.75,
                'angular_velocity': 0.95,
                'angular_acceleration': 1.5,
                'accel_limit': 0.25,
                'decel_limit': 0.30,
            }
            
            # 4. Perturbar parámetros
            perturbed_params, param_name, sigma = self.parameter_perturbator.create_perturbed_params(
                best_match_params,
                best_match['similarity_score']
            )
            self.last_perturbed_params = perturbed_params
            self.last_perturbed_param_name = param_name
            
            print(f"\n▶ Perturbación:")
            print(f"  Parámetro: {param_name}")
            print(f"  Sigma: {sigma:.4f}")
            print(f"  Cambio: {best_match_params[param_name]:.4f} → {perturbed_params[param_name]:.4f}")
            
            return {
                'status': 'ready',
                'fingerprint_7d': fp_raw,
                'best_match_id': best_match['episode_id'],
                'best_match_similarity': best_match['similarity_score'],
                'best_match_composite_score': best_match.get('composite_score', None),
                'predicted_params': perturbed_params,
                'perturbation': {
                    'parameter': param_name,
                    'sigma': sigma,
                    'original_value': best_match_params[param_name],
                    'new_value': perturbed_params[param_name]
                },
                'search_results': search_results
            }
        
        except Exception as e:
            print(f"✗ Error en pre-misión: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def post_mission_evaluation(
        self,
        mission_outcome: Dict,
        episode_id: Optional[str] = None
    ) -> Dict:
        """
        [FASE POST-MISIÓN] Evalúa resultado y registra aprendizaje.
        
        Args:
            mission_outcome: Resultado de SLAMO {
                'success': bool,
                'time_to_goal_s': float,
                'collisions': int,
                'blocked_time_s': float,
                'composite_score': float
            }
            episode_id: ID para registrar (generado si es None)
            
        Returns:
            Dict con evaluación:
            {
                'status': 'evaluated|error',
                'is_improvement': bool,
                'composite_score': float,
                'improvement_delta': float,
                'registered': bool
            }
        """
        
        print("\n" + "-" * 70)
        print("[POST-MISIÓN] Evaluación y aprendizaje")
        print("-" * 70)
        
        try:
            if self.last_best_match is None:
                raise RuntimeError("No hay pre-misión ejecutada. Llama pre_mission_prediction() primero.")
            
            # 1. Extraer composite_score
            actual_composite, valid = self.mission_evaluator.evaluate_mission_outcome(mission_outcome)
            
            print(f"▶ Outcome evaluado:")
            print(f"  Composite score: {actual_composite:.2f}")
            print(f"  Válido: {valid}")
            
            # 2. Comparar con best-match
            best_match_composite = self.last_best_match.get('composite_score', 0.0)
            is_improvement, delta = self.mission_evaluator.compare_outcomes(
                actual_composite,
                best_match_composite
            )
            
            print(f"\n▶ Comparación:")
            print(f"  Best match score: {best_match_composite:.2f}")
            print(f"  Actual score: {actual_composite:.2f}")
            print(f"  Delta: {delta:+.2f}")
            print(f"  ¿Mejora?: {is_improvement}")
            
            # 3. Registrar en log
            if episode_id is None:
                import time
                episode_id = f"ep_eval_{int(time.time() * 1000)}"
            
            if is_improvement:
                self.mission_evaluator.register_improvement(
                    episode_id=episode_id,
                    query_fp=self.last_query_fp,
                    best_match_id=self.last_best_match['episode_id'],
                    best_match_composite=best_match_composite,
                    actual_composite=actual_composite,
                    improvement_delta=delta,
                    perturbed_param=self.last_perturbed_param_name,
                    similarity_score=self.last_best_match['similarity_score'],
                    metadata={
                        'success': mission_outcome.get('success'),
                        'collisions': mission_outcome.get('collisions', 0)
                    }
                )
            else:
                self.mission_evaluator.register_failure(
                    episode_id=episode_id,
                    query_fp=self.last_query_fp,
                    best_match_id=self.last_best_match['episode_id'],
                    best_match_composite=best_match_composite,
                    actual_composite=actual_composite,
                    failure_delta=delta,
                    perturbed_param=self.last_perturbed_param_name,
                    similarity_score=self.last_best_match['similarity_score'],
                    metadata={
                        'success': mission_outcome.get('success'),
                        'collisions': mission_outcome.get('collisions', 0)
                    }
                )
            
            return {
                'status': 'evaluated',
                'is_improvement': is_improvement,
                'composite_score': actual_composite,
                'improvement_delta': delta,
                'registered': True,
                'episode_id': episode_id
            }
        
        except Exception as e:
            print(f"✗ Error en post-misión: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'status': 'error',
                'error': str(e),
                'registered': False
            }
    
    def get_learning_statistics(self) -> Dict:
        """Retorna estadísticas actuales del aprendizaje."""
        return self.mission_evaluator.get_statistics()
    
    def print_summary(self) -> None:
        """Imprime resumen completo del sistema."""
        print("\n" + "=" * 70)
        print("RESUMEN - EpisodicImprover7D")
        print("=" * 70)
        
        print(f"\n✓ Índice: {len(self.index_manager.episodes_flat)} episodios cargados")
        print(f"✓ FingerprintExtractor: Listo")
        print(f"✓ ParameterPerturbation: Listo")
        
        stats = self.get_learning_statistics()
        print(f"\n▶ Estadísticas de aprendizaje:")
        print(f"  Total misiones: {stats['total_missions']}")
        print(f"  Mejoras: {stats['improvements']}")
        print(f"  Tasa: {stats['improvement_rate']:.1f}%")


# ============================================================================
# FLUJO COMPLETO DE PRUEBA
# ============================================================================

if __name__ == "__main__":
    
    index_path = "/home/usuario/episodic_improver/episodic_memory_7d_legacy/fingerprints_index_unified_7d.json"
    log_path = "./test_episodic_improver_log.json"
    
    improver = EpisodicImprover7D(index_path, learning_log_path=log_path)
    
    # ========== FLUJO 1: Misión que MEJORA ==========
    print("\n\n### SIMULACIÓN 1: Misión que MEJORA ###\n")
    
    pred1 = improver.pre_mission_prediction(
        src_x=10.0,
        src_y=15.0,
        target_x=50.0,
        target_y=45.0,
        obstacle_density=0.45,
        estimated_distance=55.0
    )
    
    print(f"\n▶ Status predicción: {pred1['status']}")
    
    if pred1['status'] == 'ready':
        # Simular outcome de misión exitosa que MEJORÓ
        mission_outcome_1 = {
            'success': True,
            'time_to_goal_s': 42.5,
            'collisions': 0,
            'blocked_time_s': 0,
            'composite_score': 57.5  # Mejor que best-match histórico
        }
        
        eval1 = improver.post_mission_evaluation(mission_outcome_1, episode_id="prueba_ep_001")
        print(f"\n▶ Evaluación: {eval1['status']}")
        print(f"▶ ¿Mejora?: {eval1.get('is_improvement', False)}")
    
    # ========== FLUJO 2: Misión que NO MEJORA ==========
    print("\n\n### SIMULACIÓN 2: Misión que NO MEJORA ###\n")
    
    pred2 = improver.pre_mission_prediction(
        src_x=20.0,
        src_y=25.0,
        target_x=70.0,
        target_y=60.0,
        obstacle_density=0.75,
        estimated_distance=80.0
    )
    
    print(f"\n▶ Status predicción: {pred2['status']}")
    
    if pred2['status'] == 'ready':
        # Simular outcome que NO mejoró
        mission_outcome_2 = {
            'success': True,
            'time_to_goal_s': 85.3,
            'collisions': 1,
            'blocked_time_s': 3.2,
            'composite_score': 9.5  # Peor que best-match histórico
        }
        
        eval2 = improver.post_mission_evaluation(mission_outcome_2, episode_id="prueba_ep_002")
        print(f"\n▶ Evaluación: {eval2['status']}")
        print(f"▶ ¿Mejora?: {eval2.get('is_improvement', False)}")
    
    # Mostrar resumen final
    improver.print_summary()
    improver.mission_evaluator.print_statistics()
