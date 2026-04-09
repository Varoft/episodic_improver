# episodic_improver

Fingerprinting-based episodic memory system for robot navigation with adaptive parameter recommendations.

**Status:** ✅ Production-ready | **Tests:** 32/32 passing | **Phases:** 3 complete

---

## Quick Start

```bash
# Install dependencies
pip install numpy watchdog tomli pytest

# Run the system
python3 src/main.py

# Test everything
pytest tests/ -v
```

## Documentation

Most users should start here:

1. **[QUICKSTART.md](QUICKSTART.md)** ← Start here for 5-minute setup
2. **[DOCS.md](DOCS.md)** ← Complete technical reference
3. **[CHANGELOG.md](CHANGELOG.md)** ← Implementation history

## Key Features

✅ **9D Trajectory Fingerprinting** — Vector representation of robot navigation paths  
✅ **Real-time Episode Monitoring** — Automatic episode detection via filesystem events  
✅ **k-NN Similarity Retrieval** — Find comparable episodes from history  
✅ **Adaptive Recommendations** — Suggest parameter adjustments for next attempt  
✅ **TOML Configuration** — All parameters tunable without code changes  
✅ **Full Test Coverage** — 32 tests across all phases (fingerprint, integration, config)

## Project Structure

```
src/
  ├── main.py                    # Main component (EpisodicImproverComponent)
  ├── episodic_improver.py       # 9D fingerprinting engine
  ├── directory_monitor.py       # Real-time file monitoring
  ├── recommendation_engine.py   # k-NN + parameter recommendations
  └── config_manager.py          # TOML configuration management

tests/
  ├── test_fingerprint.py        # 23 unit tests (Phase 1)
  ├── test_integration_phase2.py # 5 integration tests (Phase 2)
  └── test_config.py             # 4 config tests (Phase 3)

etc/
  ├── config.toml               # Active configuration
  └── config.example.toml       # Configuration template

episodic_memory/
  └── {location}/               # Episodes grouped by location
      └── ep_*.json             # Episode files
```

## Component Overview

**Three-phase implementation:**

| Phase | Component | Purpose | Status |
|-------|-----------|---------|--------|
| 1 | FingerprintModel | 9D trajectory vectorization + k-NN | ✅ 23 tests |
| 2 | DirectoryMonitor + RecommendationEngine | Real-time streaming + recommendations | ✅ 5 tests |
| 3 | ConfigManager | TOML-based configuration | ✅ 4 tests |

---

## Usage Example

```python
from src.main import EpisodicImproverComponent
import time

# Start system
component = EpisodicImproverComponent(config_file="etc/config.toml")
component.run()

try:
    # Monitor for 60 seconds
    time.sleep(60)
    # Episodes detected automatically
    # Recommendations generated in etc/recommendations/
finally:
    component.stop()
```

---

## How It Works

1. **Add episodes** → `episodic_memory/{location}/ep_*.json`
2. **Monitor detects** → Automatically loads episode
3. **Compute fingerprint** → 9D vector representation
4. **Add query** → `etc/queries/query_*.json`
5. **Monitor detects** → Processes query
6. **Find similar** → k-NN retrieval with similarity threshold
7. **Recommend params** → Generate perturbed parameters
8. **Output** → `etc/recommendations/rec_*.json`

---

## Configuration

```toml
# etc/config.toml

[fingerprint]
outcome_quality_threshold = 0.70    # Min quality to recommend
k_neighbors = 3                      # Number of suggestions

[perturbation]
tight_sigma_pct = 3.0               # Sigma for exploitation
broad_sigma_pct = 10.0              # Sigma for exploration

[controller.max_velocity]
min = 0.1
max = 2.0

[monitoring]
ttl_seconds = 300                   # File cleanup time-to-live
```

Full configuration reference: [config.example.toml](etc/config.example.toml)

---

## Testing

```bash
# All tests
pytest tests/ -v

# By phase
pytest tests/test_fingerprint.py -v           # Phase 1 (23 tests)
pytest tests/test_integration_phase2.py -v   # Phase 2 (5 tests)
pytest tests/test_config.py -v               # Phase 3 (4 tests)

# With coverage
pytest tests/ --cov=src --cov-report=html
```

**Result:** 32/32 ✅ PASSING

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | 2.2.6 | Linear algebra (fingerprinting) |
| watchdog | latest | File system monitoring |
| tomli | latest | TOML configuration parsing |
| pytest | latest | Testing framework |

Install all:
```bash
pip install numpy==2.2.6 watchdog tomli pytest
```

---

## Next Steps

- **Setup:** Follow [QUICKSTART.md](QUICKSTART.md)
- **Understand:** Read [DOCS.md](DOCS.md) 
- **Customize:** Edit [etc/config.toml](etc/config.toml)
- **Extend:** See [CHANGELOG.md](CHANGELOG.md) for architecture insights

---

## Support

- **Configuration questions:** See [etc/config.example.toml](etc/config.example.toml) comments
- **Usage examples:** Run `pytest tests/ -v` to see working code
- **Architecture details:** See [DOCS.md](DOCS.md#architecture-overview)
- **Implementation history:** See [CHANGELOG.md](CHANGELOG.md)
