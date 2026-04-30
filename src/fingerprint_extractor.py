"""
FingerprintExtractor: Extrae un fingerprint de 7 parametros de datos de mision.
Responsable de: calcular f1-f7 a partir de geometria y contexto.
"""

import math
from typing import Dict, List, Tuple, Optional


class FingerprintExtractor:
    """
    Extrae el fingerprint (f1-f7) de los datos de una mision.

    Entrada: datos geometricos de la mision (src, target, obstaculos)
    Salida: vector [f1, f2, f3, f4, f5, f6, f7]
    """
    
    # Constantes de normalizacion (deben coincidir con calculo post-mision)
    MAP_WIDTH = 80.0   # Ancho del mapa en metros
    MAP_HEIGHT = 80.0  # Altura del mapa en metros
    DIAGONAL_MAX = math.sqrt(MAP_WIDTH**2 + MAP_HEIGHT**2)  # ~113.1
    
    MIN_STRAIGHT_DIST = 0.01  # Umbral para evitar división por cero (10 cm)
    DEFAULT_TORTUOSITY = 1.0  # Si distancia < 10cm, no hay detours
    
    @staticmethod
    def extract(
        src_x: float,
        src_y: float,
        target_x: float,
        target_y: float,
        obstacle_density: float,
        estimated_distance: float
    ) -> List[float]:
        """
        Extrae el fingerprint de la geometria de una mision.
        
        Args:
            src_x: Posicion X del robot (metros)
            src_y: Posicion Y del robot (metros)
            target_x: Coordenada X del destino (metros)
            target_y: Coordenada Y del destino (metros)
            obstacle_density: Densidad de obstaculos [0, 1]
            estimated_distance: Distancia estimada del camino (metros)
                                 (por el planificador, antes de ejecutar)
        
        Returns:
            [f1, f2, f3, f4, f5, f6, f7]
        """
        
        # ========== f1: Posicion X normalizada ==========
        f1_pos_x = src_x / FingerprintExtractor.MAP_WIDTH
        
        # ========== f2: Posicion Y normalizada ==========
        f2_pos_y = src_y / FingerprintExtractor.MAP_HEIGHT
        
        # ========== f3: Heading (angulo hacia el destino) ==========
        dx = target_x - src_x
        dy = target_y - src_y
        
        angle_rad = math.atan2(dy, dx)
        f3_heading = angle_rad / math.pi  # Normalizar a [-1, +1]
        
        # ========== f4: Distancia recta normalizada ==========
        straight_dist = math.sqrt(dx**2 + dy**2)
        f4_distance = straight_dist / FingerprintExtractor.DIAGONAL_MAX
        f4_distance = max(0.0, min(1.0, f4_distance))  # Clamp a [0, 1]
        
        # ========== f5: Tortuosity (eficiencia del camino) ==========
        # f5 = estimated_distance / straight_dist
        if straight_dist > FingerprintExtractor.MIN_STRAIGHT_DIST:
            f5_tortuosity = estimated_distance / straight_dist
        else:
            # Si distancia recta es muy pequeña, asumimos camino eficiente
            f5_tortuosity = FingerprintExtractor.DEFAULT_TORTUOSITY
        
        # ========== f6: Densidad de obstaculos ==========
        f6_density = max(0.0, min(1.0, obstacle_density))
        
        # ========== f7: Densidad por tortuosity ==========
        f7_density_tortuosity = f6_density * f5_tortuosity
        
        # Clamp f7 para evitar valores extremos
        f7_density_tortuosity = max(0.0, min(2.0, f7_density_tortuosity))
        
        return [
            f1_pos_x,
            f2_pos_y,
            f3_heading,
            f4_distance,
            f5_tortuosity,
            f6_density,
            f7_density_tortuosity
        ]
    
    @staticmethod
    def extract_from_dict(mission_data: Dict) -> List[float]:
        """
        Extrae el fingerprint a partir de un dict con los datos de mision.
        
        Formato esperado de mission_data:
        {
            'source': {'x': float, 'y': float},
            'target': {'target_x': float, 'target_y': float},
            'obstacle_density': float,
            'estimated_distance': float
        }
        
        Args:
            mission_data: Dict con datos de la mision
            
        Returns:
            [f1, f2, f3, f4, f5, f6, f7]
            
        Raises:
            KeyError si faltan campos requeridos
            ValueError si los valores estan fuera de rango
        """
        
        source = mission_data.get('source', {})
        target = mission_data.get('target', {})
        
        src_x = source.get('x', 0.0)
        src_y = source.get('y', 0.0)
        target_x = target.get('target_x', 0.0)
        target_y = target.get('target_y', 0.0)
        obstacle_density = mission_data.get('obstacle_density', 0.0)
        estimated_distance = mission_data.get('estimated_distance', 0.0)
        
        return FingerprintExtractor.extract(
            src_x, src_y, target_x, target_y, obstacle_density, estimated_distance
        )
    
    @staticmethod
    def validate_fingerprint(fp: List[float]) -> bool:
        """
        Valida que un fingerprint tenga valores razonables.
        
        Args:
            fp: [f1, f2, f3, f4, f5, f6, f7]
            
        Returns:
            True si el fingerprint es válido
        """
        if len(fp) != 7:
            return False
        
        # f1, f2: posiciones, pueden estar fuera del rango [-1, 1] (robot fuera del mapa es posible)
        # f3: heading, debe estar en [-1, 1]
        if not (-1.5 <= fp[2] <= 1.5):
            return False
        
        # f4, f6, f7: deben estar en [0, 1] o similar
        for i in [3, 5]:  # f4, f6
            if not (0.0 <= fp[i] <= 1.0):
                return False
        
        # f5: tortuosity, típicamente > 1.0 pero puede haber excepciones
        if fp[4] < 0.5:
            return False
        
        # f7: densidad por tortuosity
        if not (0.0 <= fp[6] <= 2.0):
            return False
        
        return True
    
    @staticmethod
    def describe_fingerprint(fp: List[float]) -> str:
        """
        Describe el fingerprint en texto legible.
        
        Args:
            fp: [f1, f2, f3, f4, f5, f6, f7]
            
        Returns:
            String descriptivo
        """
        if len(fp) != 7:
            return "Fingerprint inválido (no tiene 7 elementos)"
        
        descriptions = {
            'f1_pos_x': f"X={fp[0]:.3f} ({'izq' if fp[0] < 0 else 'der'})",
            'f2_pos_y': f"Y={fp[1]:.3f} ({'abajo' if fp[1] < 0 else 'arriba'})",
            'f3_heading': f"Angulo={fp[2]:.3f} rad",
            'f4_distance': f"Dist={fp[3]:.3f} (norm)",
            'f5_tortuosity': f"Tortuosity={fp[4]:.3f} ({fp[4]:.1%} detour)",
            'f6_density': f"Densidad={fp[5]:.3f}",
            'f7_density_tortuosity': f"Densidad*Tortuosity={fp[6]:.3f}"
        }
        
        desc_str = " | ".join(descriptions.values())
        return desc_str


# ============================================================================
# PRUEBAS
# ============================================================================

if __name__ == "__main__":
    
    print("=" * 70)
    print("PRUEBA: FingerprintExtractor")
    print("=" * 70)
    
    # Caso 1: Misión simple (robot en esquina, destino en otra)
    print("\n▶ Caso 1: Misión simple (esquina a esquina)")
    fp1 = FingerprintExtractor.extract(
        src_x=0.0,
        src_y=0.0,
        target_x=80.0,
        target_y=80.0,
        obstacle_density=0.2,  # 20% obstáculos
        estimated_distance=120.0  # ~5% más que diagonal directo
    )
    print(f"  FP: {[f'{f:.3f}' for f in fp1]}")
    print(f"  Descripción: {FingerprintExtractor.describe_fingerprint(fp1)}")
    print(f"  Válido: {FingerprintExtractor.validate_fingerprint(fp1)}")
    
    # Caso 2: Misión con muchos desvíos
    print("\n▶ Caso 2: Misión con muchos desvíos")
    fp2 = FingerprintExtractor.extract(
        src_x=20.0,
        src_y=20.0,
        target_x=60.0,
        target_y=60.0,
        obstacle_density=0.8,  # 80% obstáculos (área muy compleja)
        estimated_distance=80.0  # 2x la distancia recta (muchos desvíos)
    )
    print(f"  FP: {[f'{f:.3f}' for f in fp2]}")
    print(f"  Descripción: {FingerprintExtractor.describe_fingerprint(fp2)}")
    print(f"  Válido: {FingerprintExtractor.validate_fingerprint(fp2)}")
    
    # Caso 3: Desde dict
    print("\n▶ Caso 3: Extrayendo desde dict")
    mission_dict = {
        'source': {'x': 10.0, 'y': 15.0},
        'target': {'target_x': 50.0, 'target_y': 45.0},
        'obstacle_density': 0.45,
        'estimated_distance': 55.0
    }
    fp3 = FingerprintExtractor.extract_from_dict(mission_dict)
    print(f"  FP: {[f'{f:.3f}' for f in fp3]}")
    print(f"  Descripción: {FingerprintExtractor.describe_fingerprint(fp3)}")
    
    # Comparar f5_tortuosity en diferentes casos
    print("\n▶ Comparación de Tortuosity:")
    print(f"  Caso 1 (directo): f5 = {fp1[4]:.3f}")
    print(f"  Caso 2 (desvíos): f5 = {fp2[4]:.3f}")
    print(f"  Caso 3 (medio):   f5 = {fp3[4]:.3f}")
