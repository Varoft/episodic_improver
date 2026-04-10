# Flujo Completo: PRE-Misión → EJECUCIÓN → POST-Misión

**Documento para aclarar cómo funciona el aprendizaje episódico completo con ejemplos de datos reales.**

---

## 1. Los 27 Parámetros de Control del SLAMO

Estos son los parámetros de control que se pueden variar **antes** de ejecutar una misión. Se encuentran en `params_snapshot` dentro del archivo de misión:

### Parámetros del Controlador MPPI (Motion Planning)

| # | Parámetro | Rango Típico | Qué Hace |
|---|-----------|--------------|----------|
| 1 | `num_samples` | 50-500 | Cuántos caminos paralelos prueba MPPI (más = mejor pero lento) |
| 2 | `trajectory_steps` | 20-100 | Cuántos pasos en el futuro planea (horizonte de planificación) |
| 3 | `trajectory_dt` | 0.05-0.2s | Tiempo entre pasos (más pequeño = más preciso pero caro) |
| 4 | `sigma_adv` | 0.05-0.3 | Ruido en velocidad de avance (exploración) |
| 5 | `sigma_rot` | 0.05-0.3 | Ruido en rotación (exploración angular) |
| 6 | `noise_alpha` | 0.5-1.0 | Escala de ruido total en los samples |
| 7 | `mppi_lambda` | 2-20 | Parámetro de temperatura de MPPI (mayor = menos exploración) |
| 8 | `optim_iterations` | 0-10 | Iteraciones de optimización local (normalmente 0) |
| 9 | `optim_lr` | 0.01-0.1 | Learning rate para optimización |
| 10 | `warm_start_adv_weight` | 0.0-1.0 | Peso del warm-start en velocidad de avance |
| 11 | `warm_start_rot_weight` | 0.0-1.0 | Peso del warm-start en rotación |

### Parámetros de Control de Velocidad

| # | Parámetro | Rango Típico | Qué Hace |
|---|-----------|--------------|----------|
| 12 | `max_adv` | 0.3-1.5 m/s | Máxima velocidad de avance |
| 13 | `max_back_adv` | 0.1-0.5 m/s | Máxima velocidad en reversa |
| 14 | `max_rot` | 0.3-1.5 rad/s | Máxima velocidad angular |
| 15 | `velocity_smoothing` | 0.4-0.9 | Amortiguamiento de cambios de velocidad |
| 16 | `lambda_velocity` | 0.0-0.1 | Penalidad por diferencias de velocidad |

### Parámetros de Costo (Función Objetivo)

| # | Parámetro | Rango Típico | Qué Hace |
|---|-----------|--------------|----------|
| 17 | `lambda_goal` | 1-20 | Potencia del término "ir a destino" |
| 18 | `lambda_obstacle` | 1-20 | Rechazo a obstáculos |
| 19 | `lambda_smooth` | 0.01-0.5 | Suavidad del camino (penaliza giros bruscos) |
| 20 | `lambda_delta_vel` | 0.01-0.5 | Penalidad por cambios rápidos de velocidad |
| 21 | `gauss_k` | 0.1-1.0 | Suavidad de la gaussiana de obstáculos |

### Parámetros de Planificación Local

| # | Parámetro | Rango Típico | Qué Hace |
|---|-----------|--------------|----------|
| 22 | `carrot_lookahead` | 0.5-3.0 m | Distancia de look-ahead del carrot-chasing |
| 23 | `goal_threshold` | 0.1-0.5 m | Distancia aceptable al destino como "llegué" |
| 24 | `d_safe` | 0.2-0.5 m | Distancia de seguridad mínima a obstáculos |
| 25 | `safety_priority_scale` | 0.5-2.0 | Cuánto prioridad a seguridad vs objetivo |

### Parámetros Mood (Comportamiento Adaptativo)

| # | Parámetro | Rango Típico | Qué Hace |
|---|-----------|--------------|----------|
| 26 | `mood` | 0.0-1.0 | Estado emocional (0=cauteloso, 1=agresivo) |
| 27 | `mood_X_gain` (3 vars) | 0.2-0.5 | Cómo mood afecta velocidad, reactibilidad, precaución |

**TOTAL: 27 parámetros de control** que EI puede variar para optimizar misiones.

---

## 2. Estructura de Datos: Archivos en Juego

### 2.1 Archivo: `mission_initial_*.json` (Creado por SLAMO - INICIO)

**Momento:** Cuando el usuario hace clic para iniciar una misión  
**Quién lo crea:** SLAMO  
**Contenido:**

```json
{
  "mission_id": "mission_1712345678",
  "start_x": -0.624,
  "start_y": 0.532,
  "target_x": -0.371,
  "target_y": -28.367,
  "obstacle_density": 0.597,
  "estimated_distance": 28.3,
  
  "params_snapshot": {
    "base_speed": 0.35,
    "max_adv": 0.8,
    "angular_velocity": 0.7,
    ...
    // 27 parámetros iniciales (probablemente valores predeterminados)
  }
}
```

**Nota:** Los parámetros en `params_snapshot` aquí son los **iniciales** (defaults), porque aún no ha llegado la recomendación de EI.

---

### 2.2 Archivo: `predictions_*.json` (Creado por EI - PREDICCIÓN)

**Momento:** Apenas SLAMO crea `mission_initial_*.json`, EI lo detecta y genera predicciones  
**Quién lo crea:** Episodic Improver  
**Contenido:**

```json
{
  "mission_id": "mission_1712345678",
  "timestamp_ms": 1712345680000,
  "status": "ready",
  
  "fingerprint_7d": [0.0078, 0.0066, -0.25, 0.25, 1.03, 0.597, 0.615],
  //                  f1_pos_x f2_pos_y f3_heading f4_dist f5_tort f6_dens f7_complex
  
  "best_match_id": "ep_1773938714353_787241",
  "best_match_similarity": 0.92,
  
  "predicted_parameters": {
    "base_speed": 0.35,
    "max_adv": 0.85,          // ← MODIFICADO (+6.25% respecto a best-match)
    "angular_velocity": 0.7,
    // ... resto de parámetros del best-match
  },
  
  "perturbation": {
    "parameter": "max_adv",
    "sigma": 0.053,
    "original_value": 0.8,
    "new_value": 0.85
  },
  
  "search_results": [
    {
      "rank": 1,
      "episode_id": "ep_1773938714353_787241",
      "similarity_score": 0.92,
      "composite_score": 45.84
    },
    // ... rank 2, rank 3
  ]
}
```

**¿Cómo se calcula?**
1. EI lee `mission_initial_*.json`
2. Extrae: `src_x, src_y, target_x, target_y, obstacle_density, estimated_distance`
3. Calcula fingerprint 7D (primeros 4 parámetros PRE calculables, f5-f7 vienen del histórico)
4. Busca en el índice los 3 episodios más similares (usando distancia ponderada)
5. Toma el mejor match (#1)
6. Copia sus `params_snapshot`
7. Perturba UN parámetro (elegido al azar, con sigma proporcional a la similitud)
8. Guarda todo en `predictions_*.json`

---

### 2.3 Cómo SLAMO Lee las Predicciones

SLAMO debería:
1. Detectar el archivo `predictions_*.json` que EI escribió
2. Leer el `predicted_parameters`
3. Usa ESOS como `params_snapshot` en lugar de los defaults iniciales
4. Ejecuta la misión con esos parámetros

---

### 2.4 Archivo: `mission_initial_*.json` (Completado - DESPUÉS DE EJECUTAR)

**Momento:** SLAMO termina la misión  
**Quién lo modifica:** SLAMO (sobreescribiendo el archivo original o creando uno completado)  
**Contenido SE ACTUALIZA CON:**

```json
{
  // ... campos originales (mission_id, start, target, obstacle_density, etc.)
  
  "params_snapshot": {
    // ACTUALIZADO: Los parámetros que REALMENTE se usaron en la misión
    "base_speed": 0.35,
    "max_adv": 0.85,       // ← Este fue el PERTURBADO que usó
    // ... 27 parámetros actuales
  },
  
  "outcome": {
    "success_binary": 1,
    "time_to_goal_s": 54.16,
    "collisions": 0,
    "blocked_time_s": 0,
    "composite_score": 45.84,  // ← Metrica FINAL (calculada por SLAMO)
    "efficiency_score": 1.20,
    "safety_score": 0.32,
    "comfort_jerk_score": 0.61
  },
  
  "trajectory": {
    "distance_traveled_m": 28.01,
    "path_efficiency": 0.99,
    "mean_speed": 0.52,
    "max_speed": 0.75,
    "n_cycles": 724
  }
}
```

---

## 3. El Flujo Paso a Paso

### Paso 1: Usuario Cliquea en el Mapa (t=0s)

```
┌──────────────┐
│ Usuario hace │
│ clic: A → B  │
└──────┬───────┘
       │
       ↓
┌──────────────────────────┐
│ SLAMO calcula geometría  │
│ - Obtiene pos robot (src)│
│ - Obtiene destino (tgt)  │
│ - Calcula obstáculos     │
└──────────┬───────────────┘
           │
           ↓
┌──────────────────────────────┐
│ SLAMO crea mission_initial   │
│ - Escribe src, tgt, densidad │
│ - Escribe params_snapshot    │
│   (valores predeterminados)  │
└──────────┬──────────────────┘
           │
    ARCHIVO CREADO:
   mission_initial_1234.json
```

### Paso 2: EI Detecta la Misión (t=0.1s)

```
┌──────────────────────────────┐
│ DirectoryMonitor de EI       │
│ detecta mission_initial*.json │
└──────────┬──────────────────┘
           │
           ↓
┌────────────────────────┐
│ _on_mission_initial_   │
│  detected() es llamado │
└──────────┬─────────────┘
           │
           ↓
┌────────────────────────────────┐
│ EI Lee mission_initial_1234    │
│ Extrae: src_x, src_y, tgt, obs │
└────────────┬───────────────────┘
             │
             ↓
┌──────────────────────────────┐
│ Calcula fingerprint 7D:      │
│ f1 = src_x / 80  = -0.0078   │
│ f2 = src_y / 80  = +0.0066   │
│ f3 = atan2(dy,dx)/π = -0.25  │
│ f4 = dist/diag = 0.25        │
│ (f5, f6, f7 vienen del match)│
└────────────┬─────────────────┘
             │
             ↓
┌──────────────────────────────────┐
│ Busca K-NN en el índice histórico│
│ Encuentra top-3 episodios        │
│ similares (usando distancia 7D)  │
└────────────┬─────────────────────┘
```

### Paso 3: EI Genera Predicciões (t=0.2s)

```
┌────────────────────────────────┐
│ EI selecciona best-match (rank1)│
│ ep_1773938714353_787241        │
│ Similitud: 92%                 │
└────────────┬───────────────────┘
             │
             ↓
┌──────────────────────────────┐
│ EI copia params del best-match│
│ y perturba UN parámetro      │
│ Ej: max_adv: 0.80 → 0.85    │
│ (sigma = 0.053, 6.25% change) │
└────────────┬─────────────────┘
             │
             ↓
┌────────────────────────────────┐
│ EI crea predictions_1234.json  │
│ - fingerprint_7d               │
│ - best_match_id                │
│ - predicted_parameters (27 params│
│ - perturbation details          │
└────────────┬───────────────────┘
             │
    ARCHIVO CREADO:
  predictions_1234.json
```

### Paso 4: SLAMO Lee Predicciones (t=0.3s)

```
┌──────────────────────────────┐
│ SLAMO detecta predictions_*.json│
└──────────┬───────────────────┘
           │
           ↓
┌──────────────────────────────┐
│ SLAMO Lee predicted_parameters│
│ Usa ESOS en lugar de defaults │
│ (especialmente max_adv=0.85)  │
└──────────┬──────────────────┘
           │
           ↓
┌────────────────────────────────┐
│ SLAMO LANZA LA MISIÓN          │
│ con parámetros predichos       │
│ (src_x, src_y → tgt_x, tgt_y) │
└────────────┬──────────────────┘
             │
      EJECUCIÓN: 54.16 segundos
```

### Paso 5: SLAMO Completa la Misión (t=54.5s)

```
┌────────────────────────────────┐
│ SLAMO ejecuta la navegación    │
│ - Evita obstáculos            │
│ - Sigue al destino            │
│ - Registra trayectoria        │
│ - Calcula scores              │
└────────────┬───────────────────┘
             │
             ↓
┌────────────────────────────────────┐
│ SLAMO ACTUALIZA mission_initial    │
│ - Sobreescribe params_snapshot     │
│ - Añade outcome:                   │
│   • success: true                  │
│   • time_to_goal_s: 54.16         │
│   • composite_score: 45.84        │
│   • trajectory data                │
└────────────┬──────────────────────┘
             │
      ARCHIVO ACTUALIZADO:
    mission_initial_1234.json
    (ahora COMPLETO con resultados)
```

### Paso 6: EI Evalúa Resultados (POST-MISIÓN) ⭐ [PARTE MENOS CLARA]

```
┌──────────────────────────────────┐
│ DirectoryMonitor detecta que     │
│ mission_initial_*.json fue       │
│ completado/actualizado           │
│                                  │
│ (Podría ser un nuevo callback    │
│ _on_mission_outcome_detected)    │
└──────────┬──────────────────────┘
           │
           ↓
┌──────────────────────────────┐
│ EI Lee la misión completada  │
│ Extrae outcome:              │
│ {                            │
│   "composite_score": 45.84,  │ ← Puntuación REAL
│   "success": true,           │
│   "time_to_goal": 54.16,     │
│   ...                        │
│ }                            │
└────────────┬─────────────────┘
             │
             ↓
┌─────────────────────────────────────┐
│ EI Compara resultados:              │
│                                     │
│ Best-match histórico:  45.84        │
│ Nueva ejecución:       45.84        │
│ Delta: 0.0                          │
│                                     │
│ ¿Mejora? NO (pero tampoco empeoró) │
└────────────┬────────────────────────┘
             │
             ↓
┌──────────────────────────────────┐
│ EI Registra en learning_log.json │
│                                  │
│ (Ya sea en 'improvements' o       │
│  'failures' según delta)          │
│                                  │
│ Entrada:                          │
│ {                                │
│   "type": "failure" (no mejora)   │
│   "episode_id": "ep_...",         │
│   "best_match_id": "...",         │
│   "delta": 0.0,                   │
│   "perturbed_param": "max_adv",   │
│   "similarity": 0.92              │
│ }                                │
└────────────┬────────────────────┘
             │
         ¿Guardar como episodio?
         (Opción: Sí, para aprender
          incluso de fallos)
             │
             ↓
┌──────────────────────────────────┐
│ EI Guarda como NUEVO EPISODIO    │
│                                  │
│ (O actualiza el índice 7D)        │
│                                  │
│ Archivo: episodic_memory/       │
│   ep_1712345678_XXX.json        │
│                                  │
│ Contenido:                        │
│ {                                │
│   "episode_id": "ep_...",        │
│   "source": {x, y, density},     │
│   "target": {x, y},              │
│   "params_snapshot": {27 params},│
│   "outcome": {scores},           │
│   "fingerprint_7d": [7 valores], │
│   "was_prediction": true,        │
│   "predicted_from": best_match,  │
│   "perturbation": {param, sigma},│
│ }                                │
└────────────┬────────────────────┘
```

---

## 4. Lo Que Sucede en cada Punto POST-Misión ⭐

### 4.1 COMPARACIÓN DE SCORES

```
composite_score es UNA MÉTRICA ÚNICA calculada por SLAMO:

composite_score = 100 × success
                - time_to_goal_s
                - 50 × collisions
                - 2 × blocked_time_s
                
Ejemplo:
- Éxito: sí (+100)
- Tiempo: 54.16s (-54.16)
- Colisiones: 0 (-0)
- Bloqueado: 0s (-0)
─────────────────────────
composite_score = 45.84
```

### 4.2 DETERMINAR SI MEJORÓ

```
if actual_composite > best_match_composite + threshold:
    ✓ MEJORA ← Registrar como "improvement"
    → Incrementar counter de mejoras
    → Guardar en learning_log["improvements"]
else:
    ✗ NO MEJORA ← Registrar como "failure"
    → Incrementar counter de fallos
    → Guardar en learning_log["failures"]

Nota: Incluso los NO-MEJORAS son DATOS VALIOSOS
porque nos dicen qué perturbaciones NO funcionan.
```

### 4.3 GUARDAR COMO NUEVO EPISODIO

**IMPORTANTE:**
- La nueva misión (SIEMPRE, haya mejorado o no) se guarda en `episodic_memory/`
- Se añade al índice `fingerprints_index_unified_7d.json`
- En la próxima búsqueda, ESTA misión podría convertirse en best-match para otra

**Fichero Generado:**
```
episodic_memory/
  abajo_medio/
    ida/
      ep_NEW_TIMESTAMP_RANDOM.json  ← Nueva entrada
```

### 4.4 ACTUALIZAR EL ÍNDICE 7D

El archivo `fingerprints_index_unified_7d.json` se actualiza:

```json
{
  "metadata": {
    "total_items": 168,  // ← Incrementó de 167
    ...
  },
  "episodes": {
    "abajo_medio": {
      "ida": [
        {
          "episode_id": "ep_NEW_...",    ← Nueva entrada
          "fingerprint_7d": [0.0078, ...],
          "fingerprint_norm": [-0.15, ...],
          "distance_traveled_m": 28.01,
          "outcome_metrics": {
            "composite_score": 45.84,
            "success": true,
            ...
          }
        },
        // ... resto de episodios
      ]
    }
  }
}
```

---

## 5. Resumen del Flujo en 6 Pasos

| Paso | Qué Pasa | Archivo | Quién |
|------|----------|---------|-------|
| 1️⃣ **Usuario cliquea** | Determina inicio, destino, obstáculos | `mission_initial_*.json` (CREATE) | SLAMO |
| 2️⃣ **EI detecta** | Lee geometría, calcula fingerprint 7D | `mission_initial_*.json` (READ) | EI (Monitor) |
| 3️⃣ **EI predice** | Busca similar, perturba parámetros | `predictions_*.json` (CREATE) | Episodic Improver |
| 4️⃣ **SLAMO lanza** | Lee predicciones, ejecuta misión | `predictions_*.json` (READ) | SLAMO |
| 5️⃣ **SLAMO termina** | Registra outcome, scores, trayectoria | `mission_initial_*.json` (WRITE/COMPLETE) | SLAMO |
| 6️⃣ **EI evalúa** | Compara scores, registra aprendizaje, guarda episodio, actualiza índice | `learning_log.json` (APPEND), `episodic_memory/ep_*.json` (CREATE), `fingerprints_index_*.json` (UPDATE) | EI |

---

## 6. Estado Actual de la Implementación

### ✅ Implementado

- ✅ Paso 1: SLAMO crea `mission_initial_*.json`
- ✅ Paso 2-3: EI detecta, calcula fingerprint 7D, busca k-NN
- ✅ Paso 3: EI perturba parámetros
- ✅ Paso 3: EI crea `predictions_*.json`
- ✅ Paso 6 (Parcial): EI evalúa comparando scores (`mission_evaluator.py`)
- ✅ Paso 6 (Parcial): EI registra en `learning_log.json`

### ⚠️ Faltaría Completar

- ❌ Paso 4: **SLAMO NO está leyendo `predictions_*.json`** (porque SLAMO está crasheando al iniciar)
- ⚠️ Paso 5: Necesita confirmación de que SLAMO actualiza el `mission_initial_*.json` con resultados
- ⚠️ Paso 6: **Detectar cuándo la misión se completa** (podría ser un nuevo callback `_on_mission_outcome_detected`)
- ❌ Paso 6: **Guardar nuevo episodio en `episodic_memory/`** (el código existe en `main.py.save_episode()` pero nunca se llama)
- ❌ Paso 6: **Actualizar el índice 7D** (podría automatizarse)

---

## 7. Qué Debería Pasar en la Integración SLAMO ↔ EI

### Arquitectura Ideal

```
┌─────────────────────────────────────────────────────────────┐
│ SLAMO                                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Usuario selecciona nav                                │
│     └─> Crea mission_initial_*.json (geometría + defaults) │
│                                                             │
│  2. [ESPERA] Busca predictions_*.json                      │
│     └─> Si existe: Coplaca parámetros predichos           │
│     └─> Si no existe: Usa defaults                         │
│                                                             │
│  3. EJECUTA MISIÓN con parámetros                         │
│                                                             │
│  4. Termina → Actualiza mission_initial_*.json            │
│     └─> Añade outcome, trajectory, params_finales         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          ↕ (archivos JSON)
┌─────────────────────────────────────────────────────────────┐
│ EPISODIC IMPROVER                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [MONITOR] Espera archivos de misión                       │
│                                                             │
│  1. Detecta mission_initial_*.json (CREATE)                │
│     └─> PRE-MISIÓN: calcula predictions                    │
│     └─> Crea predictions_*.json                            │
│                                                             │
│  2. Detecta mission_initial_*.json (MODIFY)               │
│     └─> POST-MISIÓN: evalúa outcome                        │
│     └─> Registra aprendizaje                               │
│     └─> Guarda nuevo episodio                              │
│     └─> Actualiza índice                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Conclusión: El "Punto Poco Claro"

El usuario indicaba que **el último punto del flujo** (POST-MISIÓN) era poco claro. Esencialmente:

1. **Cuando SLAMO termina**, debe **actualizar** (no crear) el archivo `mission_initial_*.json` con los resultados
2. **EI debe detectar** este cambio (posiblemente monitorizando `MODIFY` en lugar de solo `CREATE`)
3. **EI debe evaluar** comparando `composite_score` actual vs `best_match`
4. **EI debe registrar** la mejora/fallo en `learning_log.json`
5. **EI debe guardar** la nueva misión como episodio en `episodic_memory/`
6. **EI debe actualizar** el índice `fingerprints_index_unified_7d.json` con una nueva entrada

**El sistema DETECTAR CAMBIOS en la misión es clave**, no solo crear ficheros nuevos.

Esto podría implementarse con un callback adicional en `DirectoryMonitor` que monitoreé los cambios (MODIFY events) no solo las creaciones (CREATE events).
