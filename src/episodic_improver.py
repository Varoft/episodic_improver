"""
EpisodicImprover: Orquestador del flujo pre/post mision basado en fingerprint.
"""

from typing import Dict, List, Optional

try:
    from .index_manager import IndexManager
    from .fingerprint_extractor import FingerprintExtractor
    from .parameter_perturbation import ParameterPerturbation
    from .mission_evaluator import MissionEvaluator
except ImportError:
    from index_manager import IndexManager
    from fingerprint_extractor import FingerprintExtractor
    from parameter_perturbation import ParameterPerturbation
    from mission_evaluator import MissionEvaluator


class EpisodicImprover:
    """
    Orquestador end-to-end.

    Flujo:
    1) Pre-mision: extraer fingerprint, buscar K-NN, perturbar parametros.
    2) Post-mision: comparar outcome y registrar aprendizaje.
    """

    def __init__(
        self,
        index_path: str,
        learning_log_path: str = "./episodic_memory/learning_log.json",
        index_weights: Optional[List[float]] = None
    ):
        print("Initializing EpisodicImprover")

        self.index_manager = IndexManager(index_path, weights=index_weights)
        self.fingerprint_extractor = FingerprintExtractor()
        self.parameter_perturbator = ParameterPerturbation()
        self.mission_evaluator = MissionEvaluator(learning_log_path)

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
        estimated_distance: float,
        k_neighbors: int = 3
    ) -> Dict:
        """
        Predice parametros optimizados antes de ejecutar la mision.

        Returns:
            Dict con:
            - status: ready|error
            - fingerprint: [f1..f7]
            - best_match_id
            - best_match_similarity
            - predicted_params
            - perturbation
            - search_results
        """
        print("\n" + "-" * 70)
        print("[PRE-MISION] Prediccion de parametros")
        print("-" * 70)

        try:
            fp_raw = self.fingerprint_extractor.extract(
                src_x, src_y, target_x, target_y, obstacle_density, estimated_distance
            )
            self.last_query_fp = fp_raw

            print("Fingerprint extraido:")
            print(f"  {self.fingerprint_extractor.describe_fingerprint(fp_raw)}")

            search_results = self.index_manager.search_knn(fp_raw, k=k_neighbors)
            self.last_search_results = search_results

            if not search_results:
                return {
                    "status": "error",
                    "error": "no_similar_episodes"
                }

            print("\nBusqueda K-NN:")
            for result in search_results:
                print(f"  [{result['rank']}] {result['episode_id']}")
                print(f"      Similarity: {result['similarity_score']:.1%}")

            best_match = search_results[0]
            self.last_best_match = best_match

            episode_json = self.index_manager.load_episode_json(best_match["episode_id"])
            if not episode_json:
                raise RuntimeError(f"No se pudo cargar el episodio {best_match['episode_id']}")

            best_match_params = episode_json.get("params_snapshot", {})
            if not best_match_params:
                raise RuntimeError(f"params_snapshot vacio en {best_match['episode_id']}")

            best_match_outcome = episode_json.get("outcome", {})
            best_match_composite = best_match_outcome.get("composite_score")

            perturbed_params, param_name, sigma = self.parameter_perturbator.create_perturbed_params(
                best_match_params,
                best_match["similarity_score"]
            )
            self.last_perturbed_params = perturbed_params
            self.last_perturbed_param_name = param_name

            print("\nPerturbacion:")
            print(f"  Parametro: {param_name}")
            print(f"  Sigma: {sigma:.4f}")
            print(
                f"  Cambio: {best_match_params[param_name]:.4f} -> {perturbed_params[param_name]:.4f}"
            )

            return {
                "status": "ready",
                "fingerprint": fp_raw,
                "best_match_id": best_match["episode_id"],
                "best_match_similarity": best_match["similarity_score"],
                "best_match_composite_score": best_match_composite,
                "predicted_params": perturbed_params,
                "perturbation": {
                    "parameter": param_name,
                    "sigma": sigma,
                    "original_value": best_match_params[param_name],
                    "new_value": perturbed_params[param_name]
                },
                "search_results": search_results
            }

        except Exception as e:
            print(f"Error en pre-mision: {e}")
            import traceback
            traceback.print_exc()

            return {
                "status": "error",
                "error": str(e)
            }

    def post_mission_evaluation(
        self,
        mission_outcome: Dict,
        episode_id: Optional[str] = None
    ) -> Dict:
        """
        Evalua resultado y registra aprendizaje.
        """
        print("\n" + "-" * 70)
        print("[POST-MISION] Evaluacion y aprendizaje")
        print("-" * 70)

        try:
            if self.last_best_match is None:
                raise RuntimeError("No hay pre-mision ejecutada. Llama pre_mission_prediction() primero.")

            actual_composite, valid = self.mission_evaluator.evaluate_mission_outcome(mission_outcome)

            print("Outcome evaluado:")
            print(f"  Composite score: {actual_composite:.2f}")
            print(f"  Valido: {valid}")

            best_match_composite = self.last_best_match.get("composite_score", 0.0)
            is_improvement, delta = self.mission_evaluator.compare_outcomes(
                actual_composite,
                best_match_composite
            )

            print("\nComparacion:")
            print(f"  Best match score: {best_match_composite:.2f}")
            print(f"  Actual score: {actual_composite:.2f}")
            print(f"  Delta: {delta:+.2f}")
            print(f"  Improvement?: {is_improvement}")

            if episode_id is None:
                import time
                episode_id = f"ep_eval_{int(time.time() * 1000)}"

            if is_improvement:
                self.mission_evaluator.register_improvement(
                    episode_id=episode_id,
                    query_fp=self.last_query_fp,
                    best_match_id=self.last_best_match["episode_id"],
                    best_match_composite=best_match_composite,
                    actual_composite=actual_composite,
                    improvement_delta=delta,
                    perturbed_param=self.last_perturbed_param_name,
                    similarity_score=self.last_best_match["similarity_score"],
                    metadata={
                        "success": mission_outcome.get("success"),
                        "collisions": mission_outcome.get("collisions", 0)
                    }
                )
            else:
                self.mission_evaluator.register_failure(
                    episode_id=episode_id,
                    query_fp=self.last_query_fp,
                    best_match_id=self.last_best_match["episode_id"],
                    best_match_composite=best_match_composite,
                    actual_composite=actual_composite,
                    failure_delta=delta,
                    perturbed_param=self.last_perturbed_param_name,
                    similarity_score=self.last_best_match["similarity_score"],
                    metadata={
                        "success": mission_outcome.get("success"),
                        "collisions": mission_outcome.get("collisions", 0)
                    }
                )

            return {
                "status": "evaluated",
                "is_improvement": is_improvement,
                "composite_score": actual_composite,
                "improvement_delta": delta,
                "registered": True,
                "episode_id": episode_id
            }

        except Exception as e:
            print(f"Error en post-mision: {e}")
            import traceback
            traceback.print_exc()

            return {
                "status": "error",
                "error": str(e),
                "registered": False
            }

    def get_learning_statistics(self) -> Dict:
        """Retorna estadisticas actuales del aprendizaje."""
        return self.mission_evaluator.get_statistics()

    def print_summary(self) -> None:
        """Imprime resumen completo del sistema."""
        print("\n" + "=" * 70)
        print("RESUMEN - EpisodicImprover")
        print("=" * 70)

        print(f"\nIndex: {len(self.index_manager.episodes_flat)} episodios cargados")
        print("FingerprintExtractor: listo")
        print("ParameterPerturbation: listo")

        stats = self.get_learning_statistics()
        print("\nEstadisticas de aprendizaje:")
        print(f"  Total misiones: {stats['total_missions']}")
        print(f"  Mejoras: {stats['improvements']}")
        print(f"  Tasa: {stats['improvement_rate']:.1f}%")
