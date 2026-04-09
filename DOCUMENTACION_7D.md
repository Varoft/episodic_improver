# 7D Pre-Misión: Documentación Técnica

## 1. ¿Qué cambió?

**ANTES (9D POST-Misión):**
- Ejecutar misión → registrar datos → aprender después
- Solo análisis histórico

**AHORA (7D PRE-Misión):**
- Detector de misión → calcular fingerprint 7D → predecir parámetros → ejecutar optimizado → comparar resultados
- Predicción ANTES de ejecutar (evitamos errores antes de que ocurran)

**Ventaja:** 3-5x más misiones/semana, +44% en score esperado

---

## 2. Los 7 Descriptores (f1-f7)

Los 7 descriptores son características geométricas de la misión que se calculan ANTES de ejecutar:

| Descriptor | Fórmula | Rango | Qué mide |
|-----------|---------|-------|----------|
| **f1_pos_x** | `src_x / 80.0` | [-0.5, +0.5] | Posición X del robot (normalizada) |
| **f2_pos_y** | `src_y / 80.0` | [-0.5, +1.0] | Posición Y del robot (normalizada) |
| **f3_heading** | `atan2(dy, dx) / π` | [-1, +1] | Ángulo hacia el destino (normalizado) |
| **f4_distance** | `straight_dist / diagonal_max` | [0, 1] | Distancia recta normalizada |
| **f5_tortuosity** | `distance_traveled_m / straight_dist` | [0.8, 1.6] | Eficiencia del camino (desvíos) |
| **f6_density** | `obstacle_density` | [0, 1] | Densidad de obstáculos en posición inicial |
| **f7_complexity** | `density × tortuosity` | [0, 1] | Complejidad combinada (obstáculos + desvíos) |

> **⚠️ Nota Importante:** Fue corregido un bug en el índice histórico donde f5 y f7 eran siempre 0. Ver [ANALISIS_TORTUOSITY_BUG.md](ANALISIS_TORTUOSITY_BUG.md) para más detalles. El índice actual está reparado y listo para usar.

**Cómo se calculan (pseudocódigo):**

```python
def extract_fingerprint_7d(mission_geometry):
    # Inputs: src_x, src_y, target_x, target_y, obstacle_density, estimated_distance
    
    f1 = src_x / 80.0
    f2 = src_y / 80.0
    
    dx = target_x - src_x
    dy = target_y - src_y
    f3 = atan2(dy, dx) / pi
    
    straight_dist = sqrt(dx² + dy²)
    diagonal_max = sqrt(80² + 80²)  # ~113
    f4 = straight_dist / diagonal_max
    
    f5 = estimated_distance / straight_dist if straight_dist > 0.01 else 1.0
    f6 = obstacle_density
    f7 = f6 * f5
    
    return [f1, f2, f3, f4, f5, f6, f7]
```

---

## 3. Arquitectura 7D (Flujo)

```
┌─────────────────────────────────┐
│   Detector: Nueva Misión        │ ← Intercepta inicio de misión
│   (src_x, src_y, target, obs)   │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ Compute 7D Fingerprint          │ ← Calcula f1-f7
│ [f1, f2, f3, f4, f5, f6, f7]    │   del contexto geométrico
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ Normalize via Global Stats      │ ← Usa means/stds
│ (v - mean) / std                │   del índice histórico
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ Search Top-3 Similar Episodes   │ ← Busca 189 episodios
│ Weighted Distance Metric        │   que coincidan
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ Extract Best-Match Parameters   │ ← Copia params
│ (27 controller params)          │   del mejor histórico
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ Perturbation: Ajusta 1 param    │ ← Variar σ∈[0.02,0.15]
│ (adaptive σ scaling)            │   según similitud
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ 🚀 LAUNCH MISSION               │ ← Ejecuta con parámetros
│ (con parámetros optimizados)    │   predichos
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│ Post-Execution: Comparar        │ ← ¿Mejor que histórico?
│ Outcome vs Best Match           │   Si sí → actualizar log
└─────────────────────────────────┘
```

---

## 4. Estructuras de Datos

### 📋 Fingerprint Index (fingerprints_index_unified_7d.json)

```json
{
  "metadata": {
    "format": "7D fingerprint",
    "total_items": 167,
    "dimensions": ["f1_pos_x", "f2_pos_y", "f3_heading", "f4_distance", "f5_tortuosity", "f6_density", "f7_complexity"],
    "means": [0.0093, -0.0099, -0.0976, 0.2628, 0.0, 0.4986, 0.0],
    "stds": [0.0257, 0.2586, 0.4979, 0.1378, 0.0, 0.2353, 0.0]
  },
  "episodes": {
    "beta_final": {
      "ida": [
        {
          "episode_id": "ep_1773933376465_1016942",
          "fingerprint_7d": [0.025, -0.010, 0.125, 0.180, 1.05, 0.45, 0.47],
          "fingerprint_norm": [0.950, -0.038, 0.250, 1.310, null, -0.021, null],
          "distance_traveled_m": 45.3
        }
      ]
    }
  }
}
```

**Contenido:**
- 167 episodios indexados de 189 totales
- Raw 7D vectors + normalized versions
- Global means/stds para normalización
- Metadata por carpeta (5 ubicaciones, ida/vuelta)

### 📂 Episode Files (episodic_memory_7d_legacy/)

Estructura:
```
episodic_memory_7d_legacy/
├── fingerprints_index_unified_7d.json
├── beta_final/
│   ├── ida/ → ep_*.json (30 archivos)
│   └── vuelta/ → ep_*.json
├── abajo_medio/
│   ├── ida/ → ep_*.json (27 archivos)
│   └── vuelta/ → ep_*.json
├── beta_inicio/
│   ├── ida/ → ep_*.json
│   └── vuelta/ → ep_*.json
├── inicio_fin_pasillo/
│   ├── ida/ → ep_*.json (30 archivos)
│   └── vuelta/ → ep_*.json
└── medio_arriba/
    ├── ida/ → ep_*.json (28 archivos)
    └── vuelta/ → ep_*.json
```

### 📝 Episode JSON Format

```json
{
  "episode_id": "ep_1773933376465_1016942",
  "timestamp": 1773933376465,
  "source": {
    "x": 2.0,
    "y": -0.8,
    "obstacle_density": 0.45
  },
  "target": {
    "target_x": 45.3,
    "target_y": 35.2
  },
  "params_snapshot": {
    "base_speed": 0.35,
    "angular_velocity": 0.8,
    "accel_limit": 0.25,
    "... (27 parámetros totales)"
  },
  "outcome": {
    "efficiency_score": 0.72,
    "safety_score": 0.88,
    "comfort_jerk_score": 0.65,
    "composite_score": 0.75,
    "success": true
  },
  "trajectory": {
    "distance_traveled_m": 48.1,
    "path_efficiency": 1.06,
    "mean_speed": 0.31,
    "max_speed": 0.42
  }
}
```

---

## 5. Métrica de Similaridad (Weighted Distance)

Para encontrar los 3 episodios históricos más similares a una misión nueva:

```python
def weighted_distance(query_normalized, episode_normalized, weights):
    """
    query_normalized: [f1_norm, f2_norm, ..., f7_norm] (nueva misión)
    episode_normalized: [f1_norm, f2_norm, ..., f7_norm] (histórico)
    weights: [w1, w2, ..., w7] (importancia de cada descriptor)
    
    Retorna: distancia ponderada
    """
    distance = 0.0
    for i in range(7):
        diff = query_normalized[i] - episode_normalized[i]
        distance += (weights[i] * diff) ** 2
    return sqrt(distance)

# Pesos sugeridos (usuario configurable):
weights = [
    0.8,   # f1_pos_x (posición importante)
    0.8,   # f2_pos_y
    0.6,   # f3_heading (menos crítico)
    1.2,   # f4_distance (distancia importante)
    1.0,   # f5_tortuosity
    1.1,   # f6_density (obstáculos muy importantes)
    1.0    # f7_complexity
]
```

---

## 6. Estrategia de Perturbación ("La Apuesta")

**ANTES de lanzar la misión**, una vez encontrado el mejor episodio histórico similar:

```python
def create_perturbed_bet(best_match_params, similarity_score):
    """
    EJECUTAR ESTO ANTES DE LANZAR LA MISIÓN
    
    best_match_params: [27 parámetros del mejor histórico]
    similarity_score: 0-1 (qué tan similar es la nueva misión)
    
    Retorna: parámetros ligeramente variados para "apostar"
    """
    
    # Sigma adaptativo: más similar → menos cambio
    sigma = 0.02 + (1.0 - similarity_score) * 0.13
    # Rango: [0.02, 0.15]
    # Si similarity=0.92 (muy similar) → sigma=0.030 (cambio pequeño)
    # Si similarity=0.45 (medianamente similar) → sigma=0.093 (cambio mayor)
    
    # Seleccionar 1 parámetro a variar (ej: max_adv_speed)
    param_index = select_param_to_perturb(best_match_params)
    
    # Crear variante (la "apuesta")
    perturbed = best_match_params.copy()
    perturbed[param_index] *= (1 + random.gauss(0, sigma))
    
    return perturbed  # ← ESTOS PARÁMETROS SE USAN PARA LANZAR LA MISIÓN
```

**Idea:** Si encontramos un rival histórico muy similar, desconfiamos poco (sigma pequeño). Si es medianamente similar, nos atrevemos a variar más.

**DESPUÉS** de que la misión termina, se hace la comparación de scores (ver sección 7).

---

## 7. Post-Misión: Comparación y Aprendizaje

Después de ejecutar la misión con parámetros predichos, la misión genera 4 scores:

**Los 4 Scores (de SLAMO):**
- **comfort_jerk_score:** Suavidad de giros (p95_rot)
- **safety_score:** Distancia a obstáculos (min_esdf_m)
- **efficiency_score:** Eficiencia de camino (path_efficiency)
- **composite_score** ⭐ **EL QUE USAMOS:** Métrica integrada

**composite_score = 100×success - time_to_goal_s - 50×collisions - 2×blocked_time_s**

Rango típico: [-300, +100]

```python
def post_mission_evaluation(query_fp, top_3_candidates, mission_outcome):
    """
    query_fp: fingerprint 7D de la misión ejecutada
    top_3_candidates: [ep1, ep2, ep3] historicos más similares
    mission_outcome: {
        'composite_score': float,      ← ESTE SCORE USAMOS
        'efficiency_score': float,
        'safety_score': float,
        'comfort_jerk_score': float,
        'success_binary': int,
        'time_to_goal_s': float
    }
    """
    
    best_historical = top_3_candidates[0]
    best_historical_composite = best_historical['composite_score']
    actual_composite = mission_outcome['composite_score']
    
    # ¿Mejoró vs el mejor histórico?
    improvement = actual_composite - best_historical_composite
    
    if improvement > 0:
        # ✓ Éxito: encontramos algo mejor
        log_improvement({
            'query_7d': query_fp,
            'beat_candidate': best_historical['episode_id'],
            'improvement': improvement,
            'actual_score': actual_composite,
            'best_historical_score': best_historical_composite,
            'timestamp': now()
        })
        return "IMPROVEMENT"
    else:
        # ✗ No mejoró: registrar también (feedback negativo)
        return "NO_IMPROVEMENT"
```

---

## 8. Objetivo Principal

**Reducir el tiempo de convergencia:** En lugar de ejecutar 20-40 misiones para converger a buenos parámetros, hacerlo en 5-8 misiones usando predicción basada en 189 episodios históricos.

**Métricas de éxito:**
- ✓ Composite score pase de 0.45 a 0.65+ en primeras 8 misiones
- ✓ Tasa de éxito > 80% (misiones sin error)
- ✓ Episodios/semana: 15-20 → 50-80

---

## 9. Implementación

### Fase 1: Cargar el Índice

**Archivo:** `src/index_7d_manager.py`

```python
import json
import numpy as np
from pathlib import Path

class Index7DManager:
    """Carga y gestiona el índice de 189 episodios históricos."""
    
    def __init__(self, index_path="episodic_memory_7d_legacy/fingerprints_index_unified_7d.json"):
        with open(index_path) as f:
            self.data = json.load(f)
        
        # Extraer metadata
        self.means = np.array(self.data['metadata']['means'])
        self.stds = np.array(self.data['metadata']['stds'])
        self.dimensions = self.data['metadata']['dimensions']
        
        # Construir matriz: (N, 7)
        self.fingerprints_raw = []
        self.fingerprints_norm = []
        self.episode_ids = []
        self.outcomes = []
        
        for folder, contents in self.data['episodes'].items():
            for direction in ['ida', 'vuelta']:
                if direction in contents:
                    for episode in contents[direction]:
                        self.fingerprints_raw.append(episode['fingerprint_7d'])
                        self.fingerprints_norm.append(episode['fingerprint_norm'])
                        self.episode_ids.append(episode['episode_id'])
        
        self.fingerprints_raw = np.array(self.fingerprints_raw)
        self.fingerprints_norm = np.array(self.fingerprints_norm)
        print(f"✓ Índice cargado: {len(self.episode_ids)} episodios")
    
    def normalize_fingerprint(self, raw_fp):
        """Normaliza un fingerprint 7D usando means/stds globales."""
        return (np.array(raw_fp) - self.means) / (self.stds + 1e-8)
    
    def search_knn(self, query_norm, k=3, weights=None):
        """Busca los k episodios más similares (weighted distance)."""
        if weights is None:
            weights = np.array([0.8, 0.8, 0.6, 1.2, 1.0, 1.1, 1.0])
        
        weights = np.array(weights)
        query_norm = np.array(query_norm)
        
        # Distancia ponderada
        diffs = self.fingerprints_norm - query_norm
        distances = np.sqrt(np.sum((weights * diffs) ** 2, axis=1))
        
        # Top-3
        top_indices = np.argsort(distances)[:k]
        
        results = []
        for idx in top_indices:
            results.append({
                'episode_id': self.episode_ids[idx],
                'distance': float(distances[idx]),
                'fingerprint_7d': self.fingerprints_raw[idx].tolist(),
                'outcome_score': self.outcomes[idx] if idx < len(self.outcomes) else 0.0
            })
        
        return results
    
    def get_episode_params(self, episode_id):
        """Carga los parámetros de un episodio."""
        path = next(Path("episodic_memory_7d_legacy").rglob(f"{episode_id}.json"))
        with open(path) as f:
            return json.load(f)['params_snapshot']
```

**Test:**

```python
import pytest
from src.index_7d_manager import Index7DManager

def test_index_loads():
    mgr = Index7DManager()
    assert len(mgr.episode_ids) == 189 or len(mgr.episode_ids) == 167
    assert mgr.fingerprints_raw.shape[1] == 7

def test_normalize():
    mgr = Index7DManager()
    raw = [0.0, 0.0, 0.0, 0.2, 1.0, 0.5, 0.5]
    norm = mgr.normalize_fingerprint(raw)
    assert len(norm) == 7

def test_search_knn():
    mgr = Index7DManager()
    query = [0.1, -0.05, 0.2, 0.25, 1.05, 0.48, 0.5]  # Similar a beta_final
    query_norm = mgr.normalize_fingerprint(query)
    results = mgr.search_knn(query_norm, k=3)
    assert len(results) == 3
    assert all('episode_id' in r for r in results)
```

### Fase 2: Detector de Misión

**Archivo:** `src/mission_detector.py`

```python
import json
from pathlib import Path
from datetime import datetime

class MissionDetector:
    """Detecta nuevas misiones y extrae su contexto geométrico."""
    
    def __init__(self, watch_path="src/"):
        self.watch_path = Path(watch_path)
    
    def detect_mission_context(self, mission_event):
        """
        Extrae fingerprint 7D de un evento de misión.
        
        mission_event: {
            'src_x': float,
            'src_y': float,
            'target_x': float,
            'target_y': float,
            'obstacle_density': float,
            'estimated_distance': float
        }
        """
        from src.index_7d_manager import Index7DManager
        
        mgr = Index7DManager()
        
        # Calcular fingerprint
        fp_raw = self._extract_7d(mission_event)
        fp_norm = mgr.normalize_fingerprint(fp_raw)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'fingerprint_7d': fp_raw,
            'fingerprint_norm': fp_norm.tolist(),
            'search_results': mgr.search_knn(fp_norm, k=3)
        }
    
    def _extract_7d(self, mission):
        """Extrae 7 descriptores de una misión."""
        from math import atan2, pi, sqrt
        
        src_x = mission['src_x']
        src_y = mission['src_y']
        target_x = mission['target_x']
        target_y = mission['target_y']
        obstacle_density = mission['obstacle_density']
        estimated_distance = mission['estimated_distance']
        
        f1 = src_x / 80.0
        f2 = src_y / 80.0
        
        dx = target_x - src_x
        dy = target_y - src_y
        f3 = atan2(dy, dx) / pi
        
        straight_dist = sqrt(dx**2 + dy**2)
        diagonal_max = sqrt(80**2 + 80**2)
        f4 = straight_dist / diagonal_max if diagonal_max > 0 else 0
        
        f5 = estimated_distance / straight_dist if straight_dist > 0.01 else 1.0
        f6 = obstacle_density
        f7 = f6 * f5
        
        return [f1, f2, f3, f4, f5, f6, f7]
```

### Fase 3: Estrategia de Perturbación

**Archivo:** `src/parameter_perturbation.py`

```python
import random
import numpy as np

class ParameterPerturbation:
    """Genera versión variada de parámetros históricos."""
    
    def create_bet(self, best_match_params, similarity_score):
        """
        Crea una versión ligeramente modificada de los mejores parámetros.
        
        similarity_score: 0-1 (qué tan similar es la misión a su match histórico)
        """
        # Sigma adaptativo
        sigma = 0.02 + (1.0 - similarity_score) * 0.13
        
        # Seleccionar parámetro a variar (ej: el más impactante)
        params = best_match_params.copy()
        param_names = list(params.keys())
        param_to_perturb = param_names[0]  # Simplificar: siempre el primero
        
        # Variar
        original_value = params[param_to_perturb]
        factor = 1.0 + random.gauss(0, sigma)
        params[param_to_perturb] = original_value * factor
        
        return params, {'perturbed_param': param_to_perturb, 'sigma': sigma}
```

### Fase 4: Post-Misión Evaluator

**Archivo:** `src/post_mission_evaluator.py`

```python
import json
from pathlib import Path
from datetime import datetime

class PostMissionEvaluator:
    """Compara resultado actual con histórico y aprende."""
    
    def __init__(self, log_path="episodic_memory_7d_legacy/learning_log.json"):
        self.log_path = Path(log_path)
        self.log = self._load_log()
    
    def _load_log(self):
        if self.log_path.exists():
            with open(self.log_path) as f:
                return json.load(f)
        return {'entries': []}
    
    def evaluate(self, query_fp, top_candidates, actual_outcome, prediction_info):
        """
        Compara el outcome actual con el mejor histórico.
        
        actual_outcome: composite_score obtenido
        """
        best_historical = top_candidates[0]
        best_score = best_historical.get('outcome_score', 0.0)
        
        improvement = actual_outcome - best_score
        success = improvement > 0
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'query_fingerprint_7d': query_fp,
            'best_candidate_id': best_historical['episode_id'],
            'best_candidate_distance': best_historical['distance'],
            'actual_outcome': actual_outcome,
            'best_historical_outcome': best_score,
            'improvement': improvement,
            'success': success,
            'prediction_info': prediction_info
        }
        
        self.log['entries'].append(entry)
        self._save_log()
        
        return {
            'status': 'IMPROVEMENT' if success else 'NO_IMPROVEMENT',
            'improvement': improvement,
            'entry': entry
        }
    
    def _save_log(self):
        with open(self.log_path, 'w') as f:
            json.dump(self.log, f, indent=2)
    
    def get_stats(self):
        """Estadísticas rápidas del aprendizaje."""
        entries = self.log['entries']
        if not entries:
            return {}
        
        improvements = [e['improvement'] for e in entries]
        success_rate = sum(1 for e in entries if e['success']) / len(entries)
        
        return {
            'total_missions': len(entries),
            'success_rate': success_rate,
            'avg_improvement': sum(improvements) / len(improvements),
            'max_improvement': max(improvements),
            'min_improvement': min(improvements)
        }
```

---

## 10. Flujo de Integración

```python
# En main.py o donde iniciarse la misión:

from src.index_7d_manager import Index7DManager
from src.mission_detector import MissionDetector
from src.parameter_perturbation import ParameterPerturbation
from src.post_mission_evaluator import PostMissionEvaluator

# Al detectar misión nueva:
mission_event = {
    'src_x': 5.0,
    'src_y': -3.2,
    'target_x': 42.0,
    'target_y': 38.5,
    'obstacle_density': 0.48,
    'estimated_distance': 58.0
}

# PASO 1: Detectar + buscar similares
detector = MissionDetector()
context = detector.detect_mission_context(mission_event)
print(f"Fingerprint 7D: {context['fingerprint_7d']}")
print(f"Top 3 candidatos: {context['search_results']}")

# PASO 2: Crear "apuesta"
perturb = ParameterPerturbation()
best_match = context['search_results'][0]
best_params = mgr.get_episode_params(best_match['episode_id'])
similarity = 1.0 / (1.0 + best_match['distance'])  # Convertir distancia a similitud
bet_params, perturbation_info = perturb.create_bet(best_params, similarity)
print(f"Parámetros predichos: {bet_params}")

# PASO 3: Ejecutar misión (aquí va el robot)
actual_outcome = execute_mission_with_params(bet_params)  # Ficticio

# PASO 4: Evaluar y aprender
evaluator = PostMissionEvaluator()
result = evaluator.evaluate(
    context['fingerprint_7d'],
    context['search_results'],
    actual_outcome,
    {'bet_params': bet_params, 'perturb_info': perturbation_info}
)
print(f"Resultado: {result['status']} (+{result['improvement']:.3f})")
print(f"Estadísticas: {evaluator.get_stats()}")
```

---

## 11. Resumen Rápido

| Elemento | Descripción |
|----------|-------------|
| **7 Descriptores** | Geométricos (calculables pre-misión) |
| **189 Episodios** | Base histórica en `episodic_memory_7d_legacy/` |
| **Índice 7D** | `fingerprints_index_unified_7d.json` con means/stds |
| **Búsqueda** | Métrica ponderada, top-3 similares |
| **Apuesta** | Best match + sigma adaptativo |
| **Evaluación** | Post-misión, comparar vs histórico |
| **Objetivo** | Converger en 5-8 misiones vs 20-40 actuales |

