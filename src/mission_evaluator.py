"""
MissionEvaluator: Evaluación post-misión
Responsable de: comparar composite_scores y registrar mejoras
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path


class MissionEvaluator:
    """
    Evalúa si una misión ejecutada mejoró respecto al best-match histórico.
    
    Flujo:
    1. Recibir outcome de la misión ejecutada
    2. Extraer composite_score
    3. Comparar vs best-match histórico
    4. Registrar improvement o failure (feedback para aprender)
    """
    
    def __init__(self, learning_log_path: Optional[str] = None):
        """
        Inicializa el evaluador.
        
        Args:
            learning_log_path: Ruta al archivo de log de aprendizaje
                               Si None, usa: episodic_memory/learning_log.json
        """
        if learning_log_path is None:
            learning_log_path = "./episodic_memory/learning_log.json"
        
        self.learning_log_path = Path(learning_log_path)
        self.learning_log = self._load_or_create_log()
    
    def _load_or_create_log(self) -> Dict:
        """Carga o crea el archivo de log de aprendizaje."""
        if self.learning_log_path.exists():
            try:
                with open(self.learning_log_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠ Log corrupto, creando nuevo: {self.learning_log_path}")
        
        # Crear log nuevo
        log = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'total_missions': 0,
                'improvements': 0,
                'failures': 0
            },
            'improvements': [],
            'failures': []
        }
        
        try:
            self.learning_log_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"⚠ Warning: Could not create directory {self.learning_log_path.parent}: {e}")
            print(f"  Learning log will be created but may not persist.")
        
        return log
    
    def _save_log(self) -> None:
        """Guarda el log a disco."""
        self.learning_log['metadata']['updated_at'] = datetime.now().isoformat()
        
        try:
            # Ensure parent directory exists
            self.learning_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.learning_log_path, 'w') as f:
                json.dump(self.learning_log, f, indent=2)
        except OSError as e:
            print(f"⚠ Warning: Could not save learning log to {self.learning_log_path}: {e}")
            print(f"  In-memory log updated but changes will not persist.")
    
    @staticmethod
    def evaluate_mission_outcome(mission_result: Dict) -> Tuple[float, bool]:
        """
        Extrae y valida el composite_score del resultado de la misión.
        
        Args:
            mission_result: Dict con resultado de SLAMO {
                'success': bool,
                'time_to_goal_s': float,
                'collisions': int,
                'blocked_time_s': float,
                'composite_score': float (YA CALCULADO por SLAMO)
            }
            
        Returns:
            (composite_score, is_valid)
        """
        
        # Si el score ya viene calculado, usarlo
        if 'composite_score' in mission_result:
            cs = mission_result['composite_score']
            return cs, True
        
        # Si no, recalcularlo a partir de los componentes
        try:
            success = mission_result.get('success', False)
            time_to_goal = mission_result.get('time_to_goal_s', 1000)
            collisions = mission_result.get('collisions', 0)
            blocked_time = mission_result.get('blocked_time_s', 0)
            
            composite = 100 * success - time_to_goal - 50 * collisions - 2 * blocked_time
            return composite, True
        except Exception as e:
            print(f"✗ Error calculando composite_score: {e}")
            return 0.0, False
    
    def compare_outcomes(
        self,
        actual_composite: float,
        best_match_composite: float,
        threshold: float = 0.0
    ) -> Tuple[bool, float]:
        """
        Compara el score actual con el histórico.
        
        Args:
            actual_composite: Score de la misión que acabamos de ejecutar
            best_match_composite: Score del episodio histórico similar
            threshold: Diferencia mínima para considerar "mejora" (default 0)
            
        Returns:
            (is_improvement, delta_score)
            - is_improvement: True si actual > best_match + threshold
            - delta_score: actual - best_match
        """
        
        delta = actual_composite - best_match_composite
        is_improvement = delta > threshold
        
        return is_improvement, delta
    
    def register_improvement(
        self,
        episode_id: str,
        query_fp: List[float],
        best_match_id: str,
        best_match_composite: float,
        actual_composite: float,
        improvement_delta: float,
        perturbed_param: str,
        similarity_score: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Registra una misión mejorada en el log de aprendizaje.
        
        Esta entrada se usa para:
        - Análisis histórico de qué funcionó
        - Debugging de perturbaciones exitosas
        - Estadísticas de mejora
        
        Args:
            episode_id: ID de la misión que se acaba de ejecutar
            query_fp: Fingerprint 7D de la nueva misión
            best_match_id: ID del episodio histórico similar
            best_match_composite: Composite score del histórico
            actual_composite: Composite score de la misión actual
            improvement_delta: actual - best_match
            perturbed_param: Parámetro que fue variado
            similarity_score: Similitud con el best-match
            metadata: Dict adicional con contexto
        """
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'improvement',
            'episode_id': episode_id,
            'best_match_id': best_match_id,
            'similarity_score': similarity_score,
            'improvement': {
                'delta': improvement_delta,
                'from': best_match_composite,
                'to': actual_composite
            },
            'perturbation': {
                'parameter': perturbed_param
            },
            'query_fingerprint_7d': query_fp,
            'metadata': metadata or {}
        }
        
        self.learning_log['improvements'].append(entry)
        self.learning_log['metadata']['improvements'] += 1
        self.learning_log['metadata']['total_missions'] += 1
        
        self._save_log()
        
        print(f"✓ Mejora registrada: {perturbed_param}")
        print(f"  {best_match_composite:.2f} → {actual_composite:.2f} (Δ+{improvement_delta:.2f})")
    
    def register_failure(
        self,
        episode_id: str,
        query_fp: List[float],
        best_match_id: str,
        best_match_composite: float,
        actual_composite: float,
        failure_delta: float,
        perturbed_param: str,
        similarity_score: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Registra una misión que NO mejoró (feedback negativo).
        
        Importante: Registrar también los fracasos porque son datos de aprendizaje.
        Permiten entender qué perturbaciones NO funcionan.
        
        Args:
            episode_id: ID de la misión ejecutada
            query_fp: Fingerprint 7D
            best_match_id: Episodio histórico similar
            best_match_composite: Score del histórico
            actual_composite: Score de esta misión
            failure_delta: actual - best_match (será negativo)
            perturbed_param: Parámetro que fue variado
            similarity_score: Similitud
            metadata: Contexto adicional
        """
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'failure',
            'episode_id': episode_id,
            'best_match_id': best_match_id,
            'similarity_score': similarity_score,
            'performance': {
                'delta': failure_delta,
                'from': best_match_composite,
                'to': actual_composite
            },
            'perturbation': {
                'parameter': perturbed_param
            },
            'query_fingerprint_7d': query_fp,
            'metadata': metadata or {}
        }
        
        self.learning_log['failures'].append(entry)
        self.learning_log['metadata']['failures'] += 1
        self.learning_log['metadata']['total_missions'] += 1
        
        self._save_log()
        
        print(f"✗ No-mejora registrada: {perturbed_param}")
        print(f"  {best_match_composite:.2f} → {actual_composite:.2f} (Δ{failure_delta:.2f})")
    
    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas del aprendizaje.
        
        Returns:
            Dict con:
            - total_missions: Total de misiones evaluadas
            - improvements: Cantidad de mejoras
            - improvement_rate: % de mejoras
            - avg_improvement_delta: Mejora promedio
            - avg_failure_delta: Falla promedio
        """
        
        total = self.learning_log['metadata']['total_missions']
        improvements = len(self.learning_log['improvements'])
        failures = len(self.learning_log['failures'])
        
        if total == 0:
            return {
                'total_missions': 0,
                'improvements': 0,
                'failures': 0,
                'improvement_rate': 0.0,
                'avg_improvement_delta': 0.0,
                'avg_failure_delta': 0.0
            }
        
        improvement_deltas = [imp['improvement']['delta'] for imp in self.learning_log['improvements']]
        failure_deltas = [fail['performance']['delta'] for fail in self.learning_log['failures']]
        
        avg_imp = sum(improvement_deltas) / len(improvement_deltas) if improvement_deltas else 0
        avg_fail = sum(failure_deltas) / len(failure_deltas) if failure_deltas else 0
        
        return {
            'total_missions': total,
            'improvements': improvements,
            'failures': failures,
            'improvement_rate': 100 * improvements / total,
            'avg_improvement_delta': avg_imp,
            'avg_failure_delta': avg_fail
        }
    
    def print_statistics(self) -> None:
        """Imprime estadísticas en formato legible."""
        stats = self.get_statistics()
        
        print("\n" + "=" * 60)
        print("ESTADÍSTICAS DE APRENDIZAJE")
        print("=" * 60)
        print(f"Total misiones: {stats['total_missions']}")
        print(f"Mejoras: {stats['improvements']}")
        print(f"Fracasos: {stats['failures']}")
        print(f"Tasa de mejora: {stats['improvement_rate']:.1f}%")
        
        if stats['improvements'] > 0:
            print(f"Mejora promedio: +{stats['avg_improvement_delta']:.2f}")
        
        if stats['failures'] > 0:
            print(f"Falla promedio: {stats['avg_failure_delta']:.2f}")


# ============================================================================
# PRUEBAS
# ============================================================================

if __name__ == "__main__":
    
    print("=" * 70)
    print("PRUEBA: MissionEvaluator")
    print("=" * 70)
    
    # Inicializar evaluador
    evaluator = MissionEvaluator(learning_log_path="./test_learning_log.json")
    
    # Simular misión 1: MEJORA
    print("\n▶ Caso 1: Misión que MEJORÓ respecto al histórico")
    mission_1 = {
        'success': True,
        'time_to_goal_s': 45.2,
        'collisions': 0,
        'blocked_time_s': 0,
        'composite_score': 54.8
    }
    
    best_match_1 = 43.5
    score_1, valid_1 = MissionEvaluator.evaluate_mission_outcome(mission_1)
    is_imp_1, delta_1 = evaluator.compare_outcomes(score_1, best_match_1)
    
    print(f"  Composite score actual: {score_1:.2f}")
    print(f"  Best match score: {best_match_1:.2f}")
    print(f"  ¿Mejora?: {is_imp_1} (Δ{delta_1:+.2f})")
    
    if is_imp_1:
        evaluator.register_improvement(
            episode_id="ep_new_001",
            query_fp=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
            best_match_id="ep_1773933512120_741130",
            best_match_composite=best_match_1,
            actual_composite=score_1,
            improvement_delta=delta_1,
            perturbed_param="base_speed",
            similarity_score=0.82,
            metadata={'terrain': 'indoor', 'weather': 'clear'}
        )
    
    # Simular misión 2: SIN MEJORA
    print("\n▶ Caso 2: Misión que NO mejoró")
    mission_2 = {
        'success': True,
        'time_to_goal_s': 78.5,
        'collisions': 1,
        'blocked_time_s': 2.3,
        'composite_score': -38.0
    }
    
    best_match_2 = 52.1
    score_2, valid_2 = MissionEvaluator.evaluate_mission_outcome(mission_2)
    is_imp_2, delta_2 = evaluator.compare_outcomes(score_2, best_match_2)
    
    print(f"  Composite score actual: {score_2:.2f}")
    print(f"  Best match score: {best_match_2:.2f}")
    print(f"  ¿Mejora?: {is_imp_2} (Δ{delta_2:+.2f})")
    
    if not is_imp_2:
        evaluator.register_failure(
            episode_id="ep_new_002",
            query_fp=[0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75],
            best_match_id="ep_1773937200821_177562",
            best_match_composite=best_match_2,
            actual_composite=score_2,
            failure_delta=delta_2,
            perturbed_param="angular_velocity",
            similarity_score=0.68,
            metadata={'terrain': 'outdoor', 'obstacles': 'high'}
        )
    
    # Mostrar estadísticas
    evaluator.print_statistics()
    
    # Mostrar contenido del log
    print("\n▶ Contenido del learning_log:")
    print(f"  Improvements: {len(evaluator.learning_log['improvements'])}")
    print(f"  Failures: {len(evaluator.learning_log['failures'])}")
