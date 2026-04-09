## ANÁLISIS DEL COMPONENTE SLAMO - Sistema de Episodios de Misión

### 1. UBICACIÓN Y RUTA DE ALMACENAMIENTO

**Punto de partida**: `/home/varo/robocomp/components/beta-robotica-class/ainf_slamo`

**Directorio de episodios**: `./episodic_memory/` (relativo al directorio de ejecución)

**Estructura actual**:
```
episodic_memory/
├── inicio_fin_pasillo/       # Misiones en pasillo
│   ├── ep_1773939415576_925085.json
│   ├── ep_1773939600077_241754.json
│   └── ... (30+ episodios)
└── medio_arriba/             # Misiones en zona media-superior
    ├── ep_1773939833624_956635.json
    └── ... (varios episodios)
```

**Configuración** (hardcodeada en `src/episodic_memory.h`):
```cpp
explicit EpisodicMemory(std::string root_dir = "./episodic_memory");
```

---

### 2. CÓMO SE GENERAN LAS MISIONES NUEVAS

#### Flujo de creación:

1. **Inicio de episodio** → `specificworker_navigation.cpp`
   ```cpp
   void SpecificWorker::slot_new_target(QPointF pos)
   {
       const Eigen::Vector2f target(pos.x(), pos.y());
       nav_manager_.plan_to_target(target);
       start_episode("goto_point", target);  // ← INICIA EPISODIO
   }
   ```

2. **Acumulación de métricas** → `specificworker_episode_metrics.cpp`
   - Se llama cada ciclo `compute()` (cada 100ms según config)
   - Acumula: velocidad, rotación, distancia, seguridad, CPU, etc.
   - Datos se almacenan en estructura `EpisodeAccum` en SpecificWorker

3. **Finalización y almacenamiento**
   ```cpp
   void finish_episode(const std::string &status);  // "success" o similar
   ```
   - Construye `EpisodicMemory::EpisodeRecord`
   - Llama a `episodic_memory_.save_episode(record)`
   - Guarda como archivo JSON

#### Tipos de misiones soportados:
- `"goto_point"` - Navegar a coordenada
- Potencialmente otros según configuración

#### Generación de IDs:
```cpp
static std::string make_episode_id()
{
    // Formato: ep_{timestamp_ms}_{random_20bits}
    // Ejemplo: ep_1773939415576_925085
}
```

---

### 3. FORMATO JSON DE LOS EPISODIOS

#### Ejemplo real (32 KB cada uno):

```json
{
    "episode_id": "ep_1773939415576_925085",
    "start_ts_ms": "1773939415576",
    "end_ts_ms": "1773939512765",
    "duration_s": 97.189,
    "status": "success",
    
    "mission": {
        "mission_type": "goto_point",
        "map_layout_id": "",
        "furniture_hash": "",
        "robot_context": "",
        "controller_version": "ainf_slamo_v2"
    },
    
    "source": {
        "x": 0.0189,
        "y": -27.386,
        "obstacle_density": 0.118
    },
    
    "target": {
        "target_mode": "point",
        "target_x": 0.0,
        "target_y": 26.810,
        "target_object_id": ""
    },
    
    "params_snapshot": {
        "carrot_lookahead": 2,
        "d_safe": 0.35,
        "num_samples": 100,
        "max_adv": 0.8,
        "max_rot": 0.7,
        // ... 20+ parámetros MPPI
    },
    
    "mood_snapshot": {
        "mood": 0.5,
        "mood_caution_gain": 0.3,
        "mood_reactivity_gain": 0.35,
        "mood_speed_gain": 0.35
    },
    
    "trajectory": {
        "n_cycles": 1924,
        "distance_traveled_m": 53.45,
        "path_efficiency": 1.014,
        "mean_speed": 0.594,
        "p95_speed": 0.717,
        "mean_rot": 0.167,
        "mean_ess_ratio": 0.305,
        "mean_cpu_pct": 262.6,
        "p95_mppi_ms": 0.837
    },
    
    "safety": {
        "min_esdf_m": 0.071,
        "n_collision": 1,
        "n_near_collision": 0,
        "n_blocked_events": 0,
        "n_replans": 0
    },
    
    "outcome": {
        "time_to_goal_s": 97.189,
        "success_binary": 1,
        "comfort_jerk_score": 0.567,
        "safety_score": 0.071,
        "efficiency_score": 1.014,
        "composite_score": -47.189
    },
    
    "replay": {
        "replayed": false,
        "replay_set_id": "",
        "counterfactual_trials": [],
        "local_sensitivity": {}
    }
}
```

**Categorías principales**:
- **Mission**: Tipo y contexto de la misión
- **Source/Target**: Punto inicial, final, y densidad de obstáculos
- **Trajectory**: Métricas de movimiento (velocidad, rotación, distancia)
- **Safety**: Distancia mínima, colisiones, eventos bloqueados
- **Outcome**: Éxito, tiempo, confort, segurad, eficiencia
- **Params/Mood**: Estado del controlador en ese momento
- **Replay**: Análisis contrafáctico (vacío en estos ejemplos)

---

### 4. MECANISMOS DE EXPORTACIÓN/COMPARTIR

**No hay mecanismo automático de exportación**, pero:

#### Métodos de acceso disponibles en el código C++:
```cpp
class EpisodicMemory {
    // Guardar un episodio
    bool save_episode(const EpisodeRecord& episode) const;
    
    // Cargar un episodio específico
    std::optional<EpisodeRecord> load_episode(const std::string& episode_id) const;
    
    // Listar IDs de episodios
    std::vector<std::string> list_episode_ids(std::size_t max_count = 0) const;
    
    // Cargar los N más recientes
    std::vector<EpisodeRecord> load_recent(std::size_t max_count) const;
};
```

#### Por archivo:
1. Los JSON están en texto plano → **fácil de copiar directamente**
2. ZIP de carpetas completas: `inicio_fin_pasillo.zip`, `medio_arriba.zip`
3. El navegador de archivos muestra: `cp episodic_memory/ /destino/`

---

### 5. CONFIGURACIÓN DE ALMACENAMIENTO

#### En código C++:
- **Archivo**: `src/episodic_memory.h` línea ~111
- **Parámetro**: Constructor con parámetro `root_dir`
- **Según uso en specificworker.h**: `rc::EpisodicMemory episodic_memory_;`
  - Se inicializa probablemente con valor por defecto `"./episodic_memory"`

#### En configuración TOML:
- **Archivo**: `etc/config.toml`
- **Resultado**: NO hay configuración de ruta de episodios
  - Se usa hardcodeada en el código

#### Creación automática de directorios:
```cpp
EpisodicMemory::EpisodicMemory(std::string root_dir)
    : root_dir_(std::move(root_dir))
{
    QDir dir(QString::fromStdString(root_dir_));
    if (!dir.exists())
        dir.mkpath(".");  // ← Crea automáticamente
}
```

---

### 6. INTEGRACIÓN CON episodic_improver

#### Puntos de integración recomendados:

1. **Consumir episodios SLAMO directamente**
   ```python
   # En episodic_improver
   slamo_episodes_dir = "/home/varo/robocomp/components/beta-robotica-class/ainf_slamo/episodic_memory"
   
   # Leer archivos JSON
   import json
   import os
   
   for mission_type in os.listdir(slamo_episodes_dir):
       folder = os.path.join(slamo_episodes_dir, mission_type)
       for ep_file in os.listdir(folder):
           with open(os.path.join(folder, ep_file)) as f:
               episode = json.load(f)
               # Processar episode
   ```

2. **Mapear campos de SLAMO a episodic_improver**
   
   | SLAMO | episodic_improver |
   |-------|-------------------|
   | `source` (x, y) | Ubicación inicial |
   | `target` (x, y) | Meta |
   | `trajectory.distance_traveled_m` | Distancia recorrida |
   | `trajectory.mean_speed` | Velocidad media |
   | `safety.min_esdf_m` | Distancia de seguridad |
   | `outcome.success_binary` | Éxito/fracaso |
   | `outcome.composite_score` | Score de desempeño |
   | `params_snapshot` | Configuración del controlador |

3. **Locales de episodios por categoría**
   ```
   SLAMO places:
   - inicio_fin_pasillo: Pasillo (inicio → fin)
   - medio_arriba: Zona central-superior
   
   → Mapear a "tipos de escena" en episodic_improver
   ```

4. **Crear interfaz de lectura C++**
   - Incluir `episodic_memory.h` en episodic_improver
   - Instanciar: `rc::EpisodicMemory em("../beta-robotica-class/ainf_slamo/episodic_memory")`
   - Usar `load_recent()` para obtener últimos episodios

5. **Extender episodic_improver para generar sus propios episodios**
   - Usar misma estructura JSON
   - Guardar en su `episodic_memory/` local
   - Canalizar través de `EpisodicMemory::save_episode()`

#### Desafío clave:
- **Compartir episodios entre componentes**: Ambicionador podría servir episodios vía IPC/Middleware
- **Sincronización**: SLAMO escribe continuamente, episodic_improver podría monitorear nuevos

---

### 7. ARCHIVOS CLAVE

| Archivo | Función |
|---------|---------|
| `src/episodic_memory.h` | Estructura EpisodeRecord, API principal |
| `src/episodic_memory.cpp` | Serialización JSON, guardado/carga |
| `src/specificworker.h` | Campo `episodic_memory_` |
| `src/specificworker_episode_metrics.cpp` | Acumulación de métricas durante misión |
| `src/specificworker_navigation.cpp` | `slot_new_target()` → `start_episode()` |
| `etc/config.toml` | Período de ciclo (100ms default) |

---

### 8. RESUMEN EJECUTIVO

**¿Dónde se guardan?** 
→ `./episodic_memory/{tipo_mision}/ep_{timestamp}_{random}.json`

**¿Cómo se crean?**
→ Usuario click → slot_new_target → start_episode → update_metrics (loop) → finish_episode → save_episode (JSON)

**¿Formato?**
→ JSON plano con 14 secciones (misión, trayectoria, seguridad, resultado, etc.)

**¿Compartir entre componentes?**
→ JSON es texto → copiable; API C++ disponible para cargar programáticamente

**¿Configuración ajena?**
→ Ruta de episodios hardcodeada (~./episodic_memory), no en config.toml
