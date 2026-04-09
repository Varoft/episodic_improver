"""
ParameterPerturbation: Perturbación adaptativa de parámetros
Responsable de: variar 1 parámetro según similitud (sigma adaptativo)
"""

import random
from typing import List, Dict, Tuple, Optional


class ParameterPerturbation:
    """
    Aplica perturbación adaptativa a los parámetros del mejor match histórico.
    
    Estrategia:
    - Copiar parámetros del best-match
    - Seleccionar 1 parámetro a variar
    - Usar sigma adaptativo: mayor similitud → menor cambio
    - Crear variante para ejecutar la misión (la "apuesta")
    """
    
    # Parámetros del sistema (usuario configurable)
    SIGMA_MIN = 0.02      # Cambio mínimo (cuando son muy similares)
    SIGMA_MAX = 0.15      # Cambio máximo (cuando son poco similares)
    
    # Rango de variación permitido para cada parámetro
    # Evita generar valores completamente fuera de realidad
    PARAM_RANGES = {
        'base_speed': (0.1, 0.8),
        'max_adv_speed': (0.2, 1.2),
        'angular_velocity': (0.2, 2.0),
        'angular_acceleration': (0.5, 3.0),
        'accel_limit': (0.1, 1.0),
        'decel_limit': (0.1, 1.0),
        # Agregar más según los parámetros reales
    }
    
    def __init__(self, seed: Optional[int] = None):
        """
        Inicializa el perturbador.
        
        Args:
            seed: Seed para reproducibilidad (debugging)
        """
        if seed is not None:
            random.seed(seed)
    
    @staticmethod
    def calculate_sigma(similarity_score: float) -> float:
        """
        Calcula sigma adaptativo basado en similitud.
        
        Formula: sigma = SIGMA_MIN + (1 - similarity) * (SIGMA_MAX - SIGMA_MIN)
        
        Intuitivamente:
        - Si similarity=1.0 (muy similar) → sigma=SIGMA_MIN (cambio pequeño)
        - Si similarity=0.0 (nada similar) → sigma=SIGMA_MAX (cambio grande)
        
        Args:
            similarity_score: [0, 1] donde 1 = muy similar, 0 = nada similar
            
        Returns:
            sigma: [SIGMA_MIN, SIGMA_MAX]
        """
        if not (0.0 <= similarity_score <= 1.0):
            raise ValueError(f"Similitud debe estar en [0, 1], recibido {similarity_score}")
        
        sigma = ParameterPerturbation.SIGMA_MIN + \
                (1.0 - similarity_score) * \
                (ParameterPerturbation.SIGMA_MAX - ParameterPerturbation.SIGMA_MIN)
        
        return sigma
    
    @staticmethod
    def select_parameter_to_perturb(params: Dict[str, float]) -> str:
        """
        Selecciona aleatoriamente 1 parámetro a variar.
        
        Políticas posibles (ahora: uniform random):
        - Uniform: cualquier parámetro con equiprobabilidad
        - Weighted: parámetros más importantes más a menudo
        - Adaptive: parámetros que minimizan variance
        
        Args:
            params: Dict con parámetros {name: value}
            
        Returns:
            Nombre del parámetro a variar
        """
        param_names = list(params.keys())
        
        if not param_names:
            raise ValueError("No hay parámetros para perturbar")
        
        # TODO: Implementar políticas más sofisticadas
        selected = random.choice(param_names)
        
        return selected
    
    @staticmethod
    def perturb_parameter(param_value: float, sigma: float, 
                         param_name: Optional[str] = None) -> float:
        """
        Perturba un parámetro individual.
        
        Formula: new_value = param_value * (1 + random.gauss(0, sigma))
        
        Args:
            param_value: Valor original del parámetro
            sigma: Desviación estándar de la perturbación
            param_name: Nombre del parámetro (para validación opcional)
            
        Returns:
            Nuevo valor perturbado
        """
        if param_value <= 0:
            # Si el parámetro es <= 0, usar suma en lugar de multiplicación
            perturbation = random.gauss(0, sigma * abs(param_value))
            new_value = param_value + perturbation
        else:
            # Usar multiplicación para el cambio
            # new = old * (1 + random_gaussian)
            multiplier = 1.0 + random.gauss(0, sigma)
            new_value = param_value * multiplier
        
        # Clamp a rangos razonables si es conocido el parámetro
        if param_name and param_name in ParameterPerturbation.PARAM_RANGES:
            min_val, max_val = ParameterPerturbation.PARAM_RANGES[param_name]
            new_value = max(min_val, min(max_val, new_value))
        
        return new_value
    
    @staticmethod
    def create_perturbed_params(
        best_match_params: Dict[str, float],
        similarity_score: float,
        param_to_perturb: Optional[str] = None
    ) -> Tuple[Dict[str, float], str, float]:
        """
        Crea una variante de los parámetros del best-match.
        
        ESTO ES LO QUE SE EJECUTA ANTES DE LANZAR LA MISIÓN.
        
        Args:
            best_match_params: Parámetros históricos {name: value}
            similarity_score: Similitud del mejor match [0, 1]
            param_to_perturb: Parámetro a variar (None = seleccionar aleatorio)
            
        Returns:
            (perturbed_params, selected_param, sigma)
            - perturbed_params: Dict con nuevos parámetros
            - selected_param: Nombre del parámetro que fue variado
            - sigma: Valor de sigma usado
        """
        
        # Copiar parámetros del histórico
        perturbed = best_match_params.copy()
        
        # Calcular sigma adaptativo
        sigma = ParameterPerturbation.calculate_sigma(similarity_score)
        
        # Seleccionar parámetro a variar
        if param_to_perturb is None:
            param_to_perturb = ParameterPerturbation.select_parameter_to_perturb(perturbed)
        
        # Obtener valor original
        if param_to_perturb not in perturbed:
            raise KeyError(f"Parámetro no existe: {param_to_perturb}")
        
        original_value = perturbed[param_to_perturb]
        
        # Perturbar
        new_value = ParameterPerturbation.perturb_parameter(
            original_value,
            sigma,
            param_name=param_to_perturb
        )
        
        perturbed[param_to_perturb] = new_value
        
        return perturbed, param_to_perturb, sigma
    
    @staticmethod
    def describe_perturbation(
        original_params: Dict[str, float],
        perturbed_params: Dict[str, float],
        similarity_score: float
    ) -> str:
        """
        Describe la perturbación en texto legible.
        
        Args:
            original_params: Parámetros del best-match histórico
            perturbed_params: Parámetros variados (los que se van a usar)
            similarity_score: Similitud del best-match
            
        Returns:
            String descriptivo
        """
        sigma = ParameterPerturbation.calculate_sigma(similarity_score)
        
        # Encontrar qué parámetro cambió
        changed_params = []
        for key in original_params:
            if key in perturbed_params:
                orig = original_params[key]
                pert = perturbed_params[key]
                if abs(orig - pert) > 0.0001:
                    pct_change = 100 * (pert - orig) / (abs(orig) + 0.001)
                    changed_params.append((key, orig, pert, pct_change))
        
        if not changed_params:
            return "Sin cambios de parámetros"
        
        desc = f"Perturbación (σ={sigma:.4f}, sim={similarity_score:.1%}):\n"
        for param, orig, pert, pct in changed_params:
            symbol = "↑" if pct > 0 else "↓"
            desc += f"  {param}: {orig:.4f} → {pert:.4f} {symbol}{abs(pct):.1f}%\n"
        
        return desc.rstrip()


# ============================================================================
# PRUEBAS
# ============================================================================

if __name__ == "__main__":
    
    print("=" * 70)
    print("PRUEBA: ParameterPerturbation")
    print("=" * 70)
    
    # Parámetros de ejemplo del best-match histórico
    best_match_params = {
        'base_speed': 0.35,
        'max_adv_speed': 0.75,
        'angular_velocity': 0.95,
        'angular_acceleration': 1.5,
        'accel_limit': 0.25,
        'decel_limit': 0.30,
    }
    
    # Caso 1: Alta similitud (confiamos, poco cambio)
    print("\n▶ Caso 1: Alta similitud (0.95)")
    perturbator = ParameterPerturbation(seed=42)  # Seed para reproducibilidad
    sim1 = 0.95
    pert1, param1, sigma1 = perturbator.create_perturbed_params(best_match_params, sim1)
    sigma1_calc = ParameterPerturbation.calculate_sigma(sim1)
    print(f"  Sigma calculado: {sigma1_calc:.4f} (rango: {ParameterPerturbation.SIGMA_MIN:.2f}-{ParameterPerturbation.SIGMA_MAX:.2f})")
    print(f"  Parámetro perturbado: {param1}")
    print(ParameterPerturbation.describe_perturbation(best_match_params, pert1, sim1))
    
    # Caso 2: Baja similitud (desconfiamos, cambio mayor)
    print("\n▶ Caso 2: Baja similitud (0.40)")
    perturbator2 = ParameterPerturbation()
    sim2 = 0.40
    pert2, param2, sigma2 = perturbator2.create_perturbed_params(best_match_params, sim2)
    sigma2_calc = ParameterPerturbation.calculate_sigma(sim2)
    print(f"  Sigma calculado: {sigma2_calc:.4f}")
    print(f"  Parámetro perturbado: {param2}")
    print(ParameterPerturbation.describe_perturbation(best_match_params, pert2, sim2))
    
    # Caso 3: Similitud media
    print("\n▶ Caso 3: Similitud media (0.65)")
    perturbator3 = ParameterPerturbation()
    sim3 = 0.65
    pert3, param3, sigma3 = perturbator3.create_perturbed_params(best_match_params, sim3)
    sigma3_calc = ParameterPerturbation.calculate_sigma(sim3)
    print(f"  Sigma calculado: {sigma3_calc:.4f}")
    print(f"  Parámetro perturbado: {param3}")
    print(ParameterPerturbation.describe_perturbation(best_match_params, pert3, sim3))
    
    # Demostración de la relación similitud <-> sigma
    print("\n▶ Relación similitud → sigma (comportamiento adaptativo):")
    for sim in [0.1, 0.3, 0.5, 0.7, 0.9, 0.99]:
        sigma = ParameterPerturbation.calculate_sigma(sim)
        print(f"  Similitud {sim:.0%} → σ = {sigma:.4f}")
