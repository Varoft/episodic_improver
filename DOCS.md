# Episodic Improver - Technical Documentation

Complete technical reference for the episodic memory fingerprinting system.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Fingerprinting Model](#fingerprinting-model)
4. [Configuration System](#configuration-system)
5. [API Reference](#api-reference)
6. [Usage Examples](#usage-examples)
7. [JSON Protocols](#json-protocols)
8. [Performance Characteristics](#performance-characteristics)

---

## Architecture Overview

**System Design:** Modular pipeline for episodic memory fingerprinting and parameter recommendation

```
Input Episodes (JSON)
        ↓
DirectoryMonitor (watchdog)
        ↓
FingerprintModel (9D vectorization)
        ↓
RecommendationEngine (k-NN + perturbation)
        ↓
Output Recommendations (JSON)
```

**Core Pipeline:**

1. **DirectoryMonitor** - Real-time detection of new episode files
2. **FingerprintModel** - Convert mission trajectories to 9D fingerprints
3. **RecommendationEngine** - Find similar episodes and suggest parameter adjustments
4. **ConfigManager** - Load system configuration from TOML files
5. **EpisodicImproverComponent** - Orchestrate all components

**Technology Stack:**
- Python 3.10+
- numpy 2.2.6 (linear algebra)
- watchdog (file monitoring)
- tomli (TOML parsing)
- pytest (testing)

---

## Core Components

### Component 1: DirectoryMonitor

**Purpose:** Real-time monitoring of filesystem for new episode/query events

**Location:** `src/directory_monitor.py`

**Key Classes:**
```python
class DirectoryMonitor:
    """Monitors directories for episode/query files"""
    def __init__(self, watch_dir: str, recursive: bool = True)
    def start(self) -> None
    def stop(self) -> None
    def add_episode_callback(self, callback: Callable)
    def add_query_callback(self, callback: Callable)

class EpisodeEventHandler(FileSystemEventHandler):
    """Handles episode file creation events"""
    
class QueryEventHandler(FileSystemEventHandler):
    """Handles query file creation events"""
```

**Event Callbacks:**
- Episode callback: `callback(episode_path: str, episode_data: dict) -> None`
- Query callback: `callback(query_path: str) -> None`

**Features:**
- Real-time file detection via watchdog
- Recursive directory monitoring
- TTL-based cleanup of orphaned files
- Integrated periodic cleanup task

---

### Component 2: FingerprintModel

**Purpose:** Vector representation of robot trajectories for similarity comparison

**Location:** `src/episodic_improver.py`

**Key Classes:**
```python
class FingerprintModel:
    """9D fingerprinting engine"""
    
    def compute_fingerprint(self, trajectory: List[dict]) -> np.ndarray
        """Generate 9D fingerprint from trajectory points"""
        # Returns: [avg_vel, heading_angle, tortuosity, safety, smoothness,
        #           acc_std, turn_rate, path_efficiency, outcome_quality]
    
    def query_knn(self, query_fp: np.ndarray, k: int = 3,
                  quality_threshold: float = 0.7) -> List[dict]
        """Find k most similar episodes"""
    
    def compute_perturbation(self, params: dict, success: bool,
                            sigma_pct: float = 3.0) -> dict
        """Generate perturbed parameter recommendations"""
```

**Fingerprint Dimensions (9D):**

| Dim | Name | Range | Computation |
|-----|------|-------|-------------|
| 0 | avg_velocity | [0, ∞) | mean distance/time |
| 1 | heading_angle | [-π, π] | atan2(Δy, Δx) normalized |
| 2 | tortuosity | [0, 1] | arc_length/straight_distance |
| 3 | safety_score | [0, 1] | sum(obstacle_distances) / path_length |
| 4 | smoothness_score | [0, 1] | inverse of heading_jerk |
| 5 | accel_std | [0, ∞) | std(acceleration magnitudes) |
| 6 | turn_rate | [0, 2π] | std(heading changes) |
| 7 | path_efficiency | [0, 1] | straight_line / arc_length |
| 8 | outcome_quality | [0, 1] | weighted avg of success metrics |

**Similarity Computation:**

```
weighted_cosine_similarity(fp1, fp2) = 
    dot(w ⊙ fp1, w ⊙ fp2) / (||w ⊙ fp1|| · ||w ⊙ fp2||)

where:
- w = [1.0, 0.8, 0.7, 0.9, 0.8, 0.6, 0.7, 0.8, 1.0]  (dimension weights)
- ⊙ = element-wise multiplication (Hadamard product)
```

**k-NN Query Algorithm:**

1. Compute similarity(query_fp, stored_fp_i) for all stored episodes
2. Filter by outcome_quality ≥ threshold
3. Sort by similarity (descending)
4. Return top k results with metadata

**Perturbation Strategy:**

Two modes based on similarity:

```
if similarity > threshold:
    sigma = tight_sigma_pct     # 3% - Exploit region
else:
    sigma = broad_sigma_pct     # 10% - Explore region

perturbed_param = original_param × (1 + σ × Normal(0,1))
```

---

### Component 3: RecommendationEngine

**Purpose:** Generate parameter recommendations based on Episode k-NN results

**Location:** `src/recommendation_engine.py`

**Key Classes:**
```python
class RecommendationEngine:
    """Generates parameter recommendations"""
    
    def process_query(self, query_data: dict) -> dict
        """Accept query and generate recommendations"""
    
    def _generate_recommendations(self, similar_episodes: List[dict],
                                  query_data: dict) -> List[dict]
        """Create parameter recommendations from similar episodes"""

class ParameterRange:
    """Defines min/max bounds for controller parameters"""
    min_val: float
    max_val: float
    
    def clip(self, value: float) -> float
    def noisy_sample(self) -> float
```

**Recommendation Process:**

1. Receive query episode fingerprint
2. Call `fingerprint_model.query_knn()` to find similar episodes
3. For each similar episode:
   - Extract controller parameters
   - Determine success/failure from outcome
   - Generate perturbed parameters using perturbation strategy
4. Return list of recommendations with rankings

**Output Structure:**
```json
{
  "query_episode": "ep_1773939415576_925085.json",
  "recommendations": [
    {
      "similar_episode": "ep_1773939600077_241754.json",
      "similarity": 0.92,
      "outcome": "success",
      "parameters": {
        "max_velocity": 1.15,
        "max_angular_velocity": 1.05,
        "...": "..."
      }
    }
  ]
}
```

---

### Component 4: ConfigManager

**Purpose:** Load and manage system configuration from TOML files

**Location:** `src/config_manager.py`

**Key Classes:**
```python
class ConfigManager:
    """Manages system-wide configuration"""
    
    def __init__(self, config_file: str = "etc/config.toml")
    def load(self) -> None
        """Load configuration from TOML file (uses defaults if missing)"""
    def get(self) -> Config
        """Get current configuration object"""
    def to_dict(self) -> dict
        """Export configuration to dictionary"""

@dataclass
class Config:
    """Root configuration object"""
    directories: DirectoryConfig
    monitoring: MonitoringConfig
    fingerprint: FingerprintConfig
    perturbation: PerturbationConfig
    controller: ControllerConfig
```

**Configuration Hierarchy:**

```
Config
├── DirectoryConfig
│   ├── episodic_memory: str (path to episode storage)
│   ├── queries: str (path to incoming queries)
│   ├── recommendations: str (path to store recommendations)
│   └── index: str (path to episode index/cache)
├── MonitoringConfig
│   ├── ttl_seconds: int (file cleanup time-to-live)
│   ├── cleanup_interval_seconds: int (cleanup check frequency)
│   └── recursive: bool (monitor subdirectories)
├── FingerprintConfig
│   ├── outcome_quality_threshold: float (min quality to consider)
│   ├── k_neighbors: int (number of recommendations)
│   └── similarity_weights: List[float] (9D weight vector)
├── PerturbationConfig
│   ├── tight_sigma_pct: float (exploitation σ)
│   └── broad_sigma_pct: float (exploration σ)
└── ControllerConfig
    ├── max_velocity: ParameterRangeConfig
    ├── max_angular_velocity: ParameterRangeConfig
    └── ... (more parameters)
```

**Default Configuration:**
```toml
[directories]
episodic_memory = "episodic_memory"
queries = "etc/queries"
recommendations = "etc/recommendations"
index = "etc/index"

[monitoring]
ttl_seconds = 300
cleanup_interval_seconds = 60
recursive = true

[fingerprint]
outcome_quality_threshold = 0.70
k_neighbors = 3
similarity_weights = [1.0, 0.8, 0.7, 0.9, 0.8, 0.6, 0.7, 0.8, 1.0]

[perturbation]
tight_sigma_pct = 3.0
broad_sigma_pct = 10.0

[controller.max_velocity]
min = 0.1
max = 2.0

[controller.max_angular_velocity]
min = 0.1
max = 2.0
```

---

### Component 5: EpisodicImproverComponent

**Purpose:** Orchestrate all components into unified system

**Location:** `src/main.py`

**Key Class:**
```python
class EpisodicImproverComponent:
    """Main orchestrator component"""
    
    def __init__(self, config_file: str = "etc/config.toml")
    def run(self) -> None
        """Start monitoring and recommendation loop"""
    def stop(self) -> None
        """Gracefully shutdown all components"""
```

**Initialization Flow:**

1. Load configuration from `config_file`
2. Create FingerprintModel with similarity weights from config
3. Create DirectoryMonitor pointing to episodic_memory directory
4. Create RecommendationEngine with outcome threshold and k-neighbors from config
5. Register callbacks:
   - Episode callback → update fingerprint database
   - Query callback → generate recommendations
6. Start directory monitor

**Example Usage:**
```python
from src.main import EpisodicImproverComponent

component = EpisodicImproverComponent(config_file="etc/config.toml")
component.run()  # Runs indefinitely, monitoring directories

# Shutdown
component.stop()
```

---

## Fingerprinting Model

### Algorithm Details

**Step 1: Trajectory Normalization**

Input trajectory is a list of waypoints with metadata:
```python
trajectory = [
    {
        "x": float,           # Position (meters)
        "y": float,
        "heading": float,     # Orientation (radians)
        "velocity": float,    # Linear velocity (m/s)
        "angular_velocity": float,  # Rotation (rad/s)
        "timestamp": float,   # Time (seconds)
        "obstacle_dist": float,     # Clearance (meters)
        "success": bool       # Mission outcome
    },
    # ... more waypoints
]
```

**Step 2: Feature Extraction**

Each dimension extracted independently:

```python
# Dim 0: Average Velocity
avg_velocity = total_distance / total_time

# Dim 1: Heading Angle (normalized)
heading_angle = mean(atan2(y_diffs, x_diffs)) / π  # Normalized to [-1, 1]

# Dim 2: Tortuosity
arc_length = sum(distances between consecutive points)
straight_distance = distance(start, end)
tortuosity = arc_length / straight_distance

# Dim 3: Safety Score
safety_score = sum(obstacle_distances) / path_length

# Dim 4: Smoothness Score
heading_jerk = std(angular_velocities)
smoothness_score = 1 / (1 + heading_jerk)

# Dim 5: Acceleration Std Dev
accel_std = std(acceleration magnitudes)

# Dim 6: Turn Rate
turn_rate = std(heading changes)

# Dim 7: Path Efficiency
path_efficiency = straight_distance / arc_length

# Dim 8: Outcome Quality
outcome_quality = 0.7 * (success ?) + 0.2 * smoothness_score + 0.1 * safety_score
```

**Step 3: Clamping to [0, 1] Range**

Each dimension clipped to [0, 1] except:
- avg_velocity: kept as-is (can exceed 1)
- accel_std: kept as-is (can exceed 1)

---

## Configuration System

### Loading Configuration

**Automatic Fallback:**

```python
from src.config_manager import ConfigManager

# Tries to load from etc/config.toml
# Falls back to defaults if file missing
config_mgr = ConfigManager()
config_mgr.load()
config = config_mgr.get()

# Access nested parameters
print(config.fingerprint.k_neighbors)           # 3
print(config.monitoring.ttl_seconds)            # 300
print(config.controller.max_velocity.max_val)   # 2.0
```

### Creating Custom Configuration

**TOML Format (etc/config.toml):**

```toml
[directories]
episodic_memory = "/path/to/episodes"
queries = "/path/to/queries"
recommendations = "/path/to/output"

[fingerprint]
outcome_quality_threshold = 0.75
k_neighbors = 5

[perturbation]
tight_sigma_pct = 2.0
broad_sigma_pct = 15.0

[controller.max_velocity]
min = 0.05
max = 3.0

[controller.max_angular_velocity]
min = 0.05
max = 3.0
```

### Programmatic Configuration

```python
from src.config_manager import (
    Config, DirectoryConfig, FingerprintConfig,
    ParameterRangeConfig, ControllerConfig
)

# Create from scratch
config = Config(
    directories=DirectoryConfig(
        episodic_memory="episodic_memory",
        queries="etc/queries",
        recommendations="etc/recommendations",
        index="etc/index"
    ),
    fingerprint=FingerprintConfig(
        outcome_quality_threshold=0.8,
        k_neighbors=5,
        similarity_weights=[1.0, 0.8, 0.7, 0.9, 0.8, 0.6, 0.7, 0.8, 1.0]
    ),
    controller=ControllerConfig(
        max_velocity=ParameterRangeConfig(min_val=0.1, max_val=2.0),
        max_angular_velocity=ParameterRangeConfig(min_val=0.1, max_val=2.0)
    ),
    # ... more nested configs
)

# Export to dictionary
config_dict = config_mgr.to_dict()
```

---

## API Reference

### FingerprintModel API

```python
from src.episodic_improver import FingerprintModel

# Initialize
model = FingerprintModel(similarity_weights=[1.0, 0.8, ...])

# Compute fingerprint from trajectory
fingerprint = model.compute_fingerprint(trajectory)
# Returns: np.ndarray of shape (9,), dtype float64

# Query k nearest neighbors
results = model.query_knn(
    query_fingerprint=query_fp,
    k=3,
    quality_threshold=0.7
)
# Returns: List[dict] with keys:
#   - episode_id: str
#   - fingerprint: np.ndarray
#   - similarity: float
#   - outcome_quality: float

# Generate perturbation recommendations
params = model.compute_perturbation(
    current_params={
        "max_velocity": 1.0,
        "max_angular_velocity": 0.5,
        # ...
    },
    success=True,
    sigma_pct=3.0
)
# Returns: dict with perturbed parameters
```

### DirectoryMonitor API

```python
from src.directory_monitor import DirectoryMonitor

# Initialize
monitor = DirectoryMonitor(watch_dir="episodic_memory", recursive=True)

# Register callbacks
def on_episode(path: str, data: dict):
    print(f"New episode: {path}")
    print(f"Data: {data}")

def on_query(path: str):
    print(f"New query: {path}")

monitor.add_episode_callback(on_episode)
monitor.add_query_callback(on_query)

# Control monitoring
monitor.start()
# ... run system ...
monitor.stop()
```

### RecommendationEngine API

```python
from src.recommendation_engine import RecommendationEngine

# Initialize with thresholds
engine = RecommendationEngine(
    fingerprint_model=model,
    outcome_quality_threshold=0.7,
    k_neighbors=3
)

# Process query
recommendations = engine.process_query(query_data={
    "episode_id": "ep_123.json",
    "fingerprint": query_fp,
    "trajectory": query_trajectory
})
# Returns: dict with:
#   - query_episode: str
#   - recommendations: List[dict]
```

### ConfigManager API

```python
from src.config_manager import ConfigManager

# Initialize and load
mgr = ConfigManager(config_file="etc/config.toml")
mgr.load()  # Uses defaults if file missing

# Get configuration object
config = mgr.get()

# Export to dictionary
config_dict = mgr.to_dict()

# Access nested properties
print(config.fingerprint.k_neighbors)
print(config.monitoring.ttl_seconds)
print(config.controller.max_velocity.min_val)
```

---

## Usage Examples

### Example 1: Basic Fingerprinting

```python
import numpy as np
from src.episodic_improver import FingerprintModel, EpisodeMetadata

# Initialize model
model = FingerprintModel()

# Create sample trajectory
trajectory = [
    {
        "x": 0.0, "y": 0.0,
        "heading": 0.0,
        "velocity": 1.0,
        "angular_velocity": 0.0,
        "timestamp": 0.0,
        "obstacle_dist": 2.0,
        "success": True
    },
    # ... more waypoints
]

# Compute fingerprint
fp = model.compute_fingerprint(trajectory)
print(f"Fingerprint: {fp}")
print(f"Shape: {fp.shape}")  # (9,)
print(f"Bounds: [{fp.min():.3f}, {fp.max():.3f}]")
```

### Example 2: Finding Similar Episodes

```python
# Query with similarity threshold
results = model.query_knn(
    query_fingerprint=query_fp,
    k=3,
    quality_threshold=0.7
)

for i, result in enumerate(results, 1):
    print(f"{i}. Episode: {result['episode_id']}")
    print(f"   Similarity: {result['similarity']:.3f}")
    print(f"   Quality: {result['outcome_quality']:.3f}")
```

### Example 3: End-to-End System

```python
from src.main import EpisodicImproverComponent
import time

# Start component
component = EpisodicImproverComponent(config_file="etc/config.toml")
component.run()

try:
    # Monitor for 60 seconds
    time.sleep(60)
finally:
    # Graceful shutdown
    component.stop()
```

### Example 4: Custom Configuration

```python
from src.config_manager import ConfigManager

# Load configuration
mgr = ConfigManager(config_file="etc/config.custom.toml")
mgr.load()
config = mgr.get()

# Access parameters
print(f"Threshold: {config.fingerprint.outcome_quality_threshold}")
print(f"K-neighbors: {config.fingerprint.k_neighbors}")
print(f"TTL: {config.monitoring.ttl_seconds}s")
```

---

## JSON Protocols

### Episode File Format

**File Location:** `{episodic_memory_dir}/{location_label}/ep_{timestamp}_{random}.json`

**Content:**
```json
{
  "episode_id": "ep_1773939415576_925085",
  "location": "inicio_fin_pasillo",
  "timestamp": 1773939415.576925,
  "mission": {
    "goal_x": 5.0,
    "goal_y": 5.0,
    "goal_heading": 0.0,
    "timeout_seconds": 120.0
  },
  "trajectory": [
    {
      "x": 0.0,
      "y": 0.0,
      "heading": 0.0,
      "velocity": 0.5,
      "angular_velocity": 0.0,
      "timestamp": 0.0,
      "obstacle_dist": 3.0,
      "success": true
    },
    {
      "x": 0.1,
      "y": 0.05,
      "heading": 0.05,
      "velocity": 0.6,
      "angular_velocity": 0.1,
      "timestamp": 0.1,
      "obstacle_dist": 2.8,
      "success": true
    }
  ],
  "controller_params": {
    "max_velocity": 1.0,
    "max_angular_velocity": 0.8,
    "acceleration_limit": 0.5
  }
}
```

### Query File Format

**File Location:** `{queries_dir}/query_{timestamp}_{random}.json`

**Content:**
```json
{
  "query_id": "query_1773939415576_123456",
  "timestamp": 1773939415.576925,
  "location": "inicio_fin_pasillo",
  "mission": {
    "goal_x": 5.0,
    "goal_y": 5.0,
    "goal_heading": 0.0,
    "timeout_seconds": 120.0
  },
  "trajectory": [
    {
      "x": 0.0,
      "y": 0.0,
      "heading": 0.0,
      "velocity": 0.5,
      "angular_velocity": 0.0,
      "timestamp": 0.0,
      "obstacle_dist": 3.0,
      "success": null
    }
  ],
  "controller_params": {
    "max_velocity": 0.8,
    "max_angular_velocity": 0.6
  }
}
```

### Recommendation File Format

**File Location:** `{recommendations_dir}/rec_{timestamp}_{query_id}.json`

**Content:**
```json
{
  "query_episode": "query_1773939415576_123456",
  "timestamp": 1773939415.576925,
  "recommendations": [
    {
      "rank": 1,
      "similar_episode": "ep_1773939600077_241754",
      "similarity": 0.92,
      "outcome": "success",
      "confidence": 0.92,
      "parameters": {
        "max_velocity": 1.05,
        "max_angular_velocity": 0.84,
        "acceleration_limit": 0.52
      },
      "perturbation_mode": "tight"
    },
    {
      "rank": 2,
      "similar_episode": "ep_1773940047153_33631",
      "similarity": 0.88,
      "outcome": "success",
      "confidence": 0.88,
      "parameters": {
        "max_velocity": 1.02,
        "max_angular_velocity": 0.82,
        "acceleration_limit": 0.51
      },
      "perturbation_mode": "tight"
    }
  ]
}
```

---

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Fingerprint computation | O(n) | n = trajectory length |
| Similarity computation | O(1) | Fixed 9D vectors |
| k-NN query | O(m log k) | m = stored episodes |
| Perturbation generation | O(1) | Single parameter update |
| Directory monitoring | O(1) | Event-driven |

### Space Complexity

| Component | Complexity | Notes |
|-----------|-----------|-------|
| Single fingerprint | O(1) | 9×8 bytes = 72 bytes/episode |
| Episode database | O(m) | m = number of episodes |
| Similarity cache | O(m) | Optional caching layer |

### Scalability Notes

**Tested Episode Counts:**
- Phase 2 demo: 34 episodes per location
- Similarity queries: < 5ms for 100 episodes
- Directory monitoring: Sub-second file detection

**Optimization Strategies:**
- Fingerprint caching (episode index in etc/index/)
- Lazy loading of similarity weights
- Vectorized operations via numpy
- Async file I/O with watchdog

**Known Limitations:**
- k-NN is linear in episode count (no spatial indexing)
- TOML parsing cached at startup (no hot reload)
- Single-threaded recommendation processing

---

## References

- **Fingerprinting Research:** Content-based trajectory similarity
- **k-NN Implementation:** Standard Euclidean-like similarity
- **Perturbation Strategy:** Adaptive exploration-exploitation
- **File Monitoring:** Watchdog library documentation

