# Análisis Práctico: Ejemplo Real de Misión (abajo_medio/ida)

**Análisis del archivo real:** `episodic_memory_7d_legacy/abajo_medio/ida/ep_1773938714353_787241.json`

---

## 1. Qué Te Dice Este JSON

Este archivo representa **UNA MISIÓN COMPLETADA** que ya pasó por todo el flujo:

```
Fase 1: Usuario navega de A a B ✓
Fase 2: EI genera predicciones ✓
Fase 3: SLAMO ejecuta ✓
Fase 4: Se registran resultados ✓
```

Analicemos cada sección para entender qué información tiene.

---

## 2. Sección 1: IDENTIDAD

```json
{
  "episode_id": "ep_1773938714353_787241",
  "start_ts_ms": "1773938714353",       ← Timestamp cuando EMPEZÓ
  "end_ts_ms": "1773938768515",         ← Timestamp cuando TERMINÓ
  "duration_s": 54.1619987487793,       ← Duración total
  "status": "success"                   ← La misión tuvo ÉXITO
}
```

**Info útil para debugging:** Sé exactamente cuándo pasó, cuánto tardó, y si fue exitosa.

---

## 3. Sección 2: GEOMETRÍA DE LA MISIÓN (`source`, `target`)

```json
{
  "source": {
    "x": -0.6238200664520264,           ← Posición inicial X (metros)
    "y": 0.5318528413772583,            ← Posición inicial Y (metros)
    "obstacle_density": 0.5973601341247559  ← Densidad de obstáculos [0-1]
  },
  
  "target": {
    "target_mode": "point",
    "target_x": -0.3712896406650543,    ← Destino X
    "target_y": -28.36652946472168      ← Destino Y
  }
}
```

### De aquí se extrae el FINGERPRINT 7D:

```python
# A partir de estos datos, EI calcularía:

f1_pos_x = source.x / 80.0
         = -0.6238 / 80.0
         = -0.00780                    ← Posición X normalizada

f2_pos_y = source.y / 80.0
         = 0.5319 / 80.0
         = 0.00665                     ← Posición Y normalizada

dx = target_x - source_x
   = -0.3713 - (-0.6238)
   = 0.2525

dy = target_y - source_y
   = -28.367 - 0.5319
   = -28.899

f3_heading = atan2(dy, dx) / π
           = atan2(-28.899, 0.2525) / 3.14159
           = -1.6429 / 3.14159
           = -0.523                    ← Ángulo hacia abajo (prácticamente 180°)

straight_dist = sqrt(dx² + dy²)
              = sqrt(0.2525² + 28.899²)
              = sqrt(0.0638 + 835.15)
              = 28.9                   ← Distancia recta hasta destino

diagonal_max = sqrt(80² + 80²) = 113.14

f4_distance = straight_dist / diagonal_max
            = 28.9 / 113.14
            = 0.2555                   ← Distancia normalizada (muy cercana comparada con la sala)

f5_tortuosity = distance_traveled_m / straight_dist
              = 24.03 / 28.9
              = 0.832                  ← Camino MÁS RECTO que lo directo (¡?!)
              
              # Nota: Esto es raro. Posiblemente distance_traveled sea una estimación
              # Habría que verificar cómo se calcula

f6_density = obstacle_density
           = 0.5974                    ← Bastantes obstáculos

f7_complexity = f6 * f5
              = 0.5974 * 0.832
              = 0.497                  ← Complejidad moderada
```

### ✅ Fingerprint 7D de este episodio:

```
[f1_pos_x, f2_pos_y, f3_heading, f4_distance, f5_tortuosity, f6_density, f7_complexity]
[-0.0078,  +0.0067,   -0.523,     0.256,       0.832,        0.597,      0.497]
```

**Interpretation:**
- Robot cerca del origen (f1, f2 muy pequeños)
- Viaja hacia abajo/atrás (f3 negativo)
- Distancia media (f4 = 25%)
- Pocos desvíos (f5 < 1.0, camino recta)
- Obstáculos significativos (f6 = 60%)
- Misión de complejidad moderada (f7 ≈ 0.5)

---

## 4. Sección 3: PARÁMETROS USADOS (`params_snapshot`)

**ESTOS son exactamente los 27 parámetros que se pueden perturbar:**

```json
{
  "params_snapshot": {
    
    // ===== MPPI Sampling =====
    "num_samples": 100,                 // Probó 100 caminos paralelos
    "trajectory_steps": 50,             // Planificó 50 pasos al futuro
    "trajectory_dt": 0.10,              // Espaciado temporal 100ms
    "sigma_adv": 0.11999999731779099,   // Ruido en velocidad de avance: 12%
    "sigma_rot": 0.15000000596046448,   // Ruido en rotación: 15%
    "noise_alpha": 0.800000011920929,   // Escala de ruido: 80%
    "mppi_lambda": 8,                   // Temperatura MPPI: 8 (moderada)
    "optim_iterations": 0,              // Sin optimización local
    "optim_lr": 0.05000000074505806,    // Learning rate (si hubiera optimización)
    "warm_start_adv_weight": 0.5,       // 50% peso al warm-start en avance
    "warm_start_rot_weight": 0.30000001192092896, // 30% peso en rotación
    
    // ===== Velocity Control =====
    "max_adv": 0.800000011920929,       // Máx velocidad: 0.8 m/s
    "max_back_adv": 0.20000000298023224, // Máx reversa: 0.2 m/s
    "max_rot": 0.699999988079071,       // Máx rotación: 0.7 rad/s
    "velocity_smoothing": 0.6000000238418579, // Suavidad: 60%
    "lambda_velocity": 0.009999999776482582, // Penalidad velocidad: baja
    
    // ===== Cost Function =====
    "lambda_goal": 5,                   // Ir al destino: 5 (moderado)
    "lambda_obstacle": 8,               // Evitar obstáculos: 8 (importante)
    "lambda_smooth": 0.10000000149011612, // Suavidad: baja
    "lambda_delta_vel": 0.18000000715255737, // Cambios velocidad: baja
    "gauss_k": 0.5,                     // Suavidad gaussiana: moderada
    
    // ===== Local Planning =====
    "carrot_lookahead": 2,              // Look-ahead: 2 metros
    "goal_threshold": 0.25,             // Umbral destino: 0.25 m
    "d_safe": 0.3499999940395355,       // Distancia segura: 0.35 m
    "safety_priority_scale": 1,         // Prioridad seguridad: normal
    
    // ===== Mood (Comportamiento) =====
    "mood": 0.5,                        // Estado emocional: neutral
    "mood_caution_gain": 0.30000001192092896,  // Cautela: 30%
    "mood_reactivity_gain": 0.3499999940395355, // Reactividad: 35%
    "mood_speed_gain": 0.3499999940395355      // Bonificación velocidad: 35%
  }
}
```

### 🎯 ¿Qué Significa Esta Configuración?

```
Filosofía General: EQUILIBRADO
- Prueba 100 caminos → búsqueda exhaustiva
- Velocidad media (0.8 m/s) → ni agresivo ni cauteloso
- Evita obstáculos (lambda=8) → seguridad importante
- Suave (lambda_smooth baja) → comodidad
- Mood neutral (0.5) → comportamiento estándar
```

---

## 5. Sección 4: LOS RESULTADOS (`outcome`)

**AQUÍ es donde se ve si la misión funcionó bien o mal:**

```json
{
  "outcome": {
    "success_binary": 1,                        // ✅ Éxito = 1, Fallo = 0
    "time_to_goal_s": 54.1619987487793,         // ⏱ Tardó 54.16 segundos
    "composite_score": 45.8380012512207,        // ⭐ SCORE FINAL = 45.84
    
    "efficiency_score": 1.2026275396347046,     // 120.26% (MÁS de 100%)
    "safety_score": 0.3207000195980072,         // 32.07% seguridad
    "comfort_jerk_score": 0.6101997494697571    // 61.02% comodidad
  }
}
```

### ¿Cómo se Calcula el composite_score?

```
composite_score = 100 × success
                - time_to_goal_s
                - 50 × collisions
                - 2 × blocked_time_s

En este caso:
= 100 × 1           (éxito)
- 54.16             (tiempo)
- 50 × 0            (sin colisiones)
- 2 × 0             (sin bloqueos)
─────────────────
= 45.84
```

### 📊 Interpretación de Scores:

```
efficiency_score = 120%
└─> MÁS de 100% puede significar:
    - Camino más corto que lo estimado
    - O una escala diferente en cálculo
    
safety_score = 32%
└─> BAJO (porque hubo algunos eventos de cercanía a obstáculos)
    
comfort_jerk_score = 61%
└─> MODERADO (no tan suave pero tampoco abrupto)

composite_score = 45.84
└─> SCORE FINAL: Penalizado por el TIEMPO principalmente
    (54 segundos es lo que más resta)
    Pero sin colisiones, así que no es malo
```

---

## 6. Sección 5: LA TRAYECTORIA REALIZADA (`trajectory`)

```json
{
  "trajectory": {
    "distance_traveled_m": 24.03028678894043,   // Viajó 24.03 metros
    "path_efficiency": 1.2026275396347046,      // 120% (muy eficiente)
    "mean_speed": 0.5618638396263123,           // Velocidad promedio: 0.56 m/s
    "max_speed": 0.714505672454834,             // Máximo que alcanzó: 0.71 m/s
    "n_cycles": 724,                            // Ciclos de planificación
    "mean_cpu_pct": 278.2630310058594,          // CPU promedio durante misión
    "mean_ess_ratio": 0.3261621594429016,       // ESS ratio (diversidad de muestras)
    "p05_ess_ratio": 0.18331417441368103,       // Percentil 5% de ESS
    "p95_mppi_ms": 1.6425089836120605,          // Percentil 95% latencia MPPI
    "p95_rot": 0.6101997494697571,              // Máxima rotación observada
    "p95_speed": 0.714505672454834              // Máxima velocidad observada
  }
}
```

### 💡 Insights de Trayectoria:

```
distance_traveled = 24.03m
pero distancia recta (straight_dist) = 28.9m
└─> HIZO UN ATAJO! (24 < 28.9)
    Posiblemente midió mal o evitó mejor

mean_speed = 0.56 m/s (pero max_adv = 0.8 m/s)
└─> NUNCA USÓ LA VELOCIDAD MÁXIMA
    Probablemente cauteloso por obstáculos

n_cycles = 724
└─> Replanificó MUCHO (cada cycle ≈ 75ms → 54s total)
    Normal en entornos con obstáculos

mean_cpu_pct = 278%
└─> ¡Usó MÁS del 100% en promedio!
    (en máquina multi-core, es normal)
```

---

## 7. Sección 6: INFORMACIÓN DE SEGURIDAD

```json
{
  "safety": {
    "blocked_time_s": 0,                // Nunca quedó bloqueado
    "min_esdf_m": 0.3207000195980072,   // Distancia mínima a obstáculo: 32cm
    "n_blocked_events": 0,              // Cero eventos de bloqueo
    "n_collision": 0,                   // Cero colisiones
    "n_near_collision": 0,              // Cero casi-colisiones
    "n_replans": 0                      // Cero replanificaciones de emergencia
  }
}
```

**¡EXCELENTE!** Misión completamente segura:
- No se chocó ✓
- No quedó atrapado ✓
- No tuvo que replanificar de emergencia ✓
- Mantuvo 32cm de distancia a obstáculos ✓

---

## 8. Cómo Sería Esta Misión en el FLUJO de EI

### ➡️ Paso 1: Usuario Navega

Usuario cliquea: desde `(-0.624, 0.532)` a `(-0.371, -28.367)`

### ➡️ Paso 2: SLAMO Crea mission_initial

```json
{
  "mission_id": "mission_1773938714353",
  "start_x": -0.6238,
  "start_y": 0.5319,
  "target_x": -0.3713,
  "target_y": -28.367,
  "obstacle_density": 0.5974,
  "estimated_distance": 28.9,
  "params_snapshot": {
    // Valores PREDETERMINADOS (defaults), aún NO perturbados
    "num_samples": 100,
    "max_adv": 0.75,  // ← Podría variar
    "mood": 0.4,      // ← Podría variar
    // ... 24 parámetros más con defaults
  }
}
```

### ➡️ Paso 3: EI Detecta y Predice

```
1. EI lee mission_initial
2. Calcula fingerprint 7D: [-0.0078, +0.0067, -0.523, 0.256, 0.832, 0.597, 0.497]
3. Busca similar en índice (imaginemos que encuentra a sí mismo con similitud 100%)
4. Copia sus parámetros (que son los del JSON que estamos analizando)
5. Perturba uno: digamos "max_adv": 0.8 → 0.85 (perturbación de +6.25%)
6. Crea predictions:
```

```json
{
  "mission_id": "mission_1773938714353",
  "fingerprint_7d": [-0.0078, +0.0067, -0.523, 0.256, 0.832, 0.597, 0.497],
  "best_match_id": "ep_1773938714353_787241",
  "best_match_similarity": 1.0,
  "predicted_parameters": {
    "num_samples": 100,
    "max_adv": 0.85,  // ← PERTURBADO
    "mood": 0.5,      // ← Sin cambio
    // ... resto igual al best-match
  },
  "perturbation": {
    "parameter": "max_adv",
    "original_value": 0.80,
    "new_value": 0.85,
    "sigma": 0.053
  }
}
```

### ➡️ Paso 4: SLAMO Ejecuta con Parámetros Predichos

SLAMO lee `predictions_*` y usa `max_adv: 0.85` en lugar del default.

Ejecuta la misión y obtiene score = X.XX

### ➡️ Paso 5: SLAMO Actualiza mission_initial

```json
{
  // ... campos originales ...
  "outcome": {
    "composite_score": 45.84  // ← Resultado actual
  },
  "params_snapshot": {
    "max_adv": 0.85  // ← Los que REALMENTE usó
  }
}
```

### ➡️ Paso 6: EI Evalúa POST-Misión

```
EI compara:
- best_match_score: 45.84
- actual_score: 45.84
- Delta: 0.0
- ¿Mejora?: NO (pero tampoco empeoró)

Registra en learning_log:
{
  "type": "failure",  // No fue mejora
  "episode_id": "ep_....",
  "best_match_id": "ep_1773938714353_787241",
  "delta": 0.0,
  "perturbed_param": "max_adv",
  "similarity": 1.0
}

Guarda nuevo episodio en episodic_memory/
{
  "source": {x, y, density},
  "target": {x, y},
  "outcome": {score: 45.84, ...},
  "params": {27 parámetros},
  "predicted_from": "ep_1773938714353_787241",
  "perturbation": {...}
}

Actualiza índice 7D:
- Añade nueva entrada
- Total episodios: 168 (de 167)
```

---

## 9. Qué Nos Enseña Este Ejemplo

### ✅ Lo Bien Hecho

1. **Seguridad perfecta** → 0 colisiones, 0 bloqueos
2. **Eficiencia buena** → 120% (camino eficiente)
3. **Comodidad aceptable** → 61% suavidad
4. **Parámetros equilibrados** → Ni agresivo ni cauteloso

### ⚠️ Oportunidades de Mejora

1. **Velocidad baja** → Solo usó 56% de la velocidad máxima permitida
   - **Perturbación propuesta:** Aumentar `max_adv` a 0.9 m/s
   - **Esperado:** Mismo resultado, pero más rápido → mejor composite_score

2. **Muchas replanificaciones** → 724 ciclos en 54 segundos
   - **Perturbación propuesta:** Aumentar `trajectory_steps` a 75
   - **Esperado:** Menos ciclos, planificación a más largo plazo

3. **Seguridad bajo** → Solo 32% en safety_score
   - **Perturbación propuesta:** Aumentar `lambda_obstacle` de 8 a 12
   - **Esperado:** Mejor evitación, posible aumento de safety_score

---

## 10. Cómo EI Elegiría Qué Perturbar

EpisodicImprover tiene un `ParameterPerturbation` que:

1. **Elige parámetro al azar** (uno de los 27)
2. **Calcula sigma basado en similitud:**
   - Si similitud 95%+: sigma pequeño (2-5%) → cambio conservador
   - Si similitud 50-75%: sigma medio (5-15%) → cambio moderado
   - Si similitud <50%: sigma grande (15-30%) → cambio agresivo

3. **Para este ejemplo con similitud=1.0:**
   - Sigma = ~5% como máximo
   - `max_adv: 0.8 → 0.8 ± 0.04 → 0.76-0.84`

---

## 11. Validación: "¿Está Todo Correcto?"

Revisando el archivo:

| Aspecto | ✓ Correcto | Nota |
|---------|-----------|------|
| Fingerprint calculable | ✅ | source, target, obstacle_density presentes |
| 27 parámetros | ✅ | Todos están en params_snapshot |
| Outcome scores | ✅ | composite_score bien calculado |
| Safety metrics | ✅ | Razas, collisions, blocked_time |
| Trajectory data | ✅ | Distance, efficiency, speeds presentes |
| Status/success | ✅ | success_binary = 1 (éxito) |

**Conclusión:** El archivo es **COMPLETO** y tiene TODO lo que EI necesita.

