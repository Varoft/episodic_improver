# Episodic Improver - Quick Start Guide

Get the system running in 5 minutes.

---

## Installation

### 1. Install Dependencies

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate

# Install requirements
pip install numpy==2.2.6 watchdog tomli pytest
```

### 2. Directory Structure

System expects these directories (created automatically):

```
episodic_improver/
├── episodic_memory/       # Episode storage (auto-monitored)
│   └── {location_label}/
├── etc/
│   ├── config.toml        # Configuration file
│   ├── queries/           # Incoming query files
│   ├── recommendations/   # Output recommendations
│   └── index/             # Episode cache
├── src/
│   ├── main.py           # Main component
│   ├── episodic_improver.py    # Fingerprinting
│   ├── directory_monitor.py    # File monitoring
│   ├── recommendation_engine.py # k-NN engine
│   └── config_manager.py       # Configuration
└── tests/                 # Test suite
```

---

## Configuration

### Quick Setup

```bash
# Create configuration file from template
cp etc/config.example.toml etc/config.toml

# Edit to customize (optional - defaults work fine)
# nano etc/config.toml
```

### Key Configuration Options

**Fingerprinting Accuracy:**
```toml
[fingerprint]
outcome_quality_threshold = 0.70  # Higher = more selective matches
k_neighbors = 3                   # Number of recommendations
```

**Parameter Ranges:**
```toml
[controller.max_velocity]
min = 0.1
max = 2.0

[controller.max_angular_velocity]
min = 0.1
max = 2.0
```

**Monitoring:**
```toml
[monitoring]
ttl_seconds = 300          # How long to keep query/rec files
cleanup_interval_seconds = 60
```

---

## Usage

### Option 1: Run Main Component

```bash
# Start monitoring in background
python3 src/main.py &

# Or run in foreground
python3 src/main.py
```

### Option 2: Interactive Python

```python
from src.main import EpisodicImproverComponent
import time

# Initialize
component = EpisodicImproverComponent(config_file="etc/config.toml")
component.run()

try:
    time.sleep(60)  # Monitor for 60 seconds
finally:
    component.stop()
```

---

## Testing

### Run All Tests

```bash
# Full test suite (27 tests)
pytest tests/ -v

# Specific test file
pytest tests/test_fingerprint.py -v

# With coverage
pytest tests/ --cov=src
```

### Quick Test

```bash
# Run one unit test
pytest tests/test_fingerprint.py::TestFingerprintComputation::test_fingerprint_shape -v
```

---

## Fingerprint Database Management

The system stores computed fingerprints in a persistent JSON database for fast querying and analysis.

### View Database Statistics

```bash
# Show database overview (episodes count, quality metrics, locations)
python3 tools/inspect_fingerprints.py stats
```

Output:
```
Total episodes:    58
Locations:         2
Quality Metrics:
  Average quality:   0.623
  Min quality:       0.550
  Max quality:       0.659
  Success rate:      100.0%
```

### Browse Episodes

```bash
# List all episodes sorted by quality (highest first)
python3 tools/inspect_fingerprints.py list

# Limit to top N episodes
python3 tools/inspect_fingerprints.py list --limit 10

# Sort by episode ID or location
python3 tools/inspect_fingerprints.py list --sort id
```

### Inspect Single Episode

```bash
# Show detailed info with 9D fingerprint
python3 tools/inspect_fingerprints.py show ep_1773939908340_155602
```

Output includes 9D fingerprint, quality scores, and success metrics.

### Search Episodes

```bash
# Find episodes by location
python3 tools/inspect_fingerprints.py search --location inicio_fin_pasillo

# Find high-quality episodes
python3 tools/inspect_fingerprints.py search --quality 0.65

# Combine filters
python3 tools/inspect_fingerprints.py search --location medio_arriba --quality 0.62
```

### Manage Fingerprints

```bash
# Add all episodes from episodic_memory/ to database
python3 tools/add_fingerprints.py batch

# Add single episode manually (for testing)
python3 tools/add_fingerprints.py single episodic_memory/location/ep_NEW.json

# Show database info
python3 tools/add_fingerprints.py info
```

### Export for Analysis

```bash
# Export database to CSV for external analysis
python3 tools/inspect_fingerprints.py export --output analysis.csv
```

**Database Location:** `etc/fingerprint_database.json` (automatically created and updated)

---

## Input/Output Formats

### Adding Episodes

1. **Create Episode File:**
   ```bash
   # File: episodic_memory/{location}/ep_{timestamp}_{random}.json
   episodic_memory/inicio_fin_pasillo/ep_1773939415576_925085.json
   ```

2. **JSON Structure:**
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
         "x": 0.0, "y": 0.0,
         "heading": 0.0,
         "velocity": 0.5,
         "angular_velocity": 0.0,
         "timestamp": 0.0,
         "obstacle_dist": 3.0,
         "success": true
       },
       { "x": 0.1, "y": 0.05, "heading": 0.05, "..." : "..." }
     ],
     "controller_params": {
       "max_velocity": 1.0,
       "max_angular_velocity": 0.8
     }
   }
   ```

### Adding Queries

1. **Create Query File:**
   ```bash
   # File: etc/queries/query_{timestamp}_{random}.json
   etc/queries/query_1773939415576_123456.json
   ```

2. **JSON Structure (same as episode, but success=null):**
   ```json
   {
     "query_id": "query_1773939415576_123456",
     "location": "inicio_fin_pasillo",
     "mission": { "..." : "..." },
     "trajectory": [
       { "x": 0.0, "y": 0.0, "...", "success": null }
     ],
     "controller_params": { "..." : "..." }
   }
   ```

### Reading Recommendations

**System generates:**
```json
{
  "query_episode": "query_1773939415576_123456",
  "recommendation": [
    {
      "rank": 1,
      "similar_episode": "ep_1773939600077_241754",
      "similarity": 0.92,
      "parameters": {
        "max_velocity": 1.05,
        "max_angular_velocity": 0.84
      }
    }
  ]
}
```

**Location:** `etc/recommendations/rec_{timestamp}_{query_id}.json`

---

## Common Tasks

### Task 1: Add Custom Location

```bash
# Create directory for new location
mkdir -p episodic_memory/new_location

# System automatically monitors subdirectories
# Add episodes: episodic_memory/new_location/ep_*.json
```

### Task 2: Change Similarity Weights

```toml
# In etc/config.toml
[fingerprint]
similarity_weights = [1.2, 0.7, 0.6, 1.0, 0.8, 0.5, 0.7, 0.8, 1.1]
#                     vel headang tort safe smooth accel turn_rate path_eff outcome
```

### Task 3: Adjust Recommendation Parameters

```toml
# In etc/config.toml

# Return more recommendations
[fingerprint]
k_neighbors = 5              # Was 3

# More aggressive exploration
[perturbation]
broad_sigma_pct = 15.0       # Was 10.0
tight_sigma_pct = 5.0        # Was 3.0

# Tighter similarity threshold
[fingerprint]
outcome_quality_threshold = 0.80    # Was 0.70
```

### Task 4: Programmatic Access

```python
from src.episodic_improver import FingerprintModel
from src.config_manager import ConfigManager

# Load config
mgr = ConfigManager("etc/config.toml")
mgr.load()
config = mgr.get()

# Create fingerprint model with config weights
model = FingerprintModel(
    similarity_weights=config.fingerprint.similarity_weights
)

# Compute fingerprint
fp = model.compute_fingerprint(trajectory)

# Query k-NN
results = model.query_knn(
    query_fp,
    k=config.fingerprint.k_neighbors,
    quality_threshold=config.fingerprint.outcome_quality_threshold
)

print(f"Found {len(results)} similar episodes")
for r in results:
    print(f"  - {r['episode_id']}: similarity={r['similarity']:.2f}")
```

---

## Troubleshooting

### Problem: Import Errors

**Solution:** Ensure you're in correct directory:
```bash
cd /home/varo/robocomp/components/episodic_improver
python3 src/main.py  # Not: python3 main.py
```

### Problem: Configuration Not Loading

**Solution:** Check file path:
```bash
# Verify config file exists
ls -la etc/config.toml

# Check for TOML syntax errors (valid YAML format)
python3 -c "import tomli; print(tomli.load(open('etc/config.toml', 'rb')))"
```

### Problem: No Recommendations Generated

**Solution:** Verify episode files exist:
```bash
# Check episodes were monitored
ls -la episodic_memory/*/

# Run single query test
python3 -m pytest tests/test_fingerprint.py::TestKNN::test_knn_returns_k -v
```

### Problem: Tests Failing

**Solution:** Check dependencies:
```bash
# Verify all packages installed
pip list | grep -E "numpy|watchdog|tomli|pytest"

# Run single simple test
pytest tests/test_fingerprint.py::TestFingerprintComputation::test_fingerprint_shape -v
```

---

## Performance Tips

### Optimize for Large Episode Databases

1. **Increase cleanup TTL** (keep episodes longer):
   ```toml
   [monitoring]
   ttl_seconds = 600  # 10 minutes
   ```

2. **Adjust k-neighbors** based on recommendation quality:
   ```toml
   [fingerprint]
   k_neighbors = 5  # More recommendations
   ```

3. **Index episodes** to speed up queries:
   - System automatically creates `etc/index/` cache
   - No manual action needed

### Monitor System Health

```bash
# Check episode count
find episodic_memory -name "*.json" | wc -l

# Check recommendation queue
ls -la etc/recommendations/ | wc -l

# Monitor process
ps aux | grep main.py
```

---

## Next Steps

- **Advanced Setup:** See [DOCS.md](DOCS.md) for detailed configuration
- **Architecture Details:** See [DOCS.md](DOCS.md#architecture-overview)
- **Phase History:** See [CHANGELOG.md](CHANGELOG.md)

---

## Support

- **Configuration Help:** See config.example.toml inline comments
- **Test Examples:** Run `pytest tests/ -v` to see working code
- **Source Comments:** Check `src/*.py` files for implementation details
