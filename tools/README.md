# Tools - Utility Scripts

This directory contains auxiliary scripts for managing fingerprint data and episodic memory.

## Scripts Overview

### `add_fingerprints.py` - Fingerprint Database Management

Manage the fingerprint database: add episodes, scan directories, and maintain the JSON database.

**Usage:**

```bash
# Batch-add all episodes from episodic_memory directory
python3 tools/add_fingerprints.py batch

# Add a single episode
python3 tools/add_fingerprints.py single episodic_memory/location/ep_12345_67890.json

# Show database information
python3 tools/add_fingerprints.py info
```

**What it does:**
- Reads episode JSON files from SLAMO format
- Extracts mission characteristics (source, target, trajectory, safety)
- Computes 9D fingerprints using FingerprintModel
- Stores all fingerprints in `etc/fingerprint_database.json`
- Organized by location for fast lookup

**Output:**
```
Total episodes:    58
Added:             58
Location counts:   {'inicio_fin_pasillo': 30, 'medio_arriba': 28}
Avg quality:       0.623
Quality range:     [0.550, 0.659]
Success rate:      100.0%
```

---

### `inspect_fingerprints.py` - Browse Fingerprints

Inspect and analyze the fingerprint database with multiple viewing modes.

**Usage:**

```bash
# Show database statistics
python3 tools/inspect_fingerprints.py stats

# List episodes (sorted by quality)
python3 tools/inspect_fingerprints.py list --limit 10
python3 tools/inspect_fingerprints.py list --location inicio_fin_pasillo

# Show details of specific episode
python3 tools/inspect_fingerprints.py show ep_1773939415576_925085
python3 tools/inspect_fingerprints.py show ep_1773939415576_925085 --verbose

# Search by criteria
python3 tools/inspect_fingerprints.py search --location medio_arriba --quality 0.65
python3 tools/inspect_fingerprints.py search --quality 0.60 --limit 15

# Export to CSV
python3 tools/inspect_fingerprints.py export --output fingerprints.csv
```

**Output Examples:**

```
# Statistics
Database Statistics
  Total episodes:    58
  Locations:         2
  Average quality:   0.623
  Success rate:      100.0%

# Episode listing
#    Episode ID                     Loc                  Quality  Success Distance  
1    ep_1773939908340_155602        medio_arriba         0.659    ✓       23.42     
2    ep_1773941750434_95825         medio_arriba         0.659    ✓       24.14

# Episode details
Episode ID: ep_1773939908340_155602
Location:   medio_arriba
Fingerprint (9D):
  start_x     :   0.4810
  start_y     :   0.8294
  end_x       :   0.4924
  end_y       :   0.5244
  heading     :  -0.4881
  ...
```

---

## Fingerprint Database Structure

The database is stored in `etc/fingerprint_database.json` with this structure:

```json
{
  "version": "1.0",
  "generated_at": "2026-04-06T13:54:02Z",
  "fingerprints_by_location": {
    "inicio_fin_pasillo": [
      {
        "episode_id": "ep_1773939415576_925085",
        "location": "inicio_fin_pasillo",
        "fingerprint": [0.5002, 0.1577, 0.5000, 0.8351, 0.5001, 0.9580, 1.0000, 0.1182, 0.0473],
        "start_x": 0.0189,
        "start_y": -27.3856,
        "end_x": 0.0,
        "end_y": 26.8096,
        "estimated_distance": 53.45,
        "obstacle_density": 0.1182,
        "efficiency_score": 1.0139,
        "safety_score": 0.0707,
        "smoothness_score": 0.5671,
        "outcome_quality": 0.5665,
        "success_binary": 1,
        "time_to_goal_s": 97.189,
        "composite_score": -47.189,
        "params_snapshot": { ... },
        "timestamp_ms": 1773939415576
      }
    ],
    "medio_arriba": [ ... ]
  },
  "metadata": {
    "total_episodes": 58,
    "locations": ["inicio_fin_pasillo", "medio_arriba"],
    "last_updated": "2026-04-06T13:54:02Z"
  }
}
```

**Fields explained:**

- **fingerprint**: 9D vector
  - [0-1]: Normalized start position (x, y)
  - [2-3]: Normalized end position (x, y)
  - [4]: Heading angle (normalized)
  - [5]: Distance metric
  - [6]: Tortuosity
  - [7]: Obstacle density
  - [8]: Hardness composite

- **Quality scores**:
  - `efficiency_score`: Path efficiency (≥ 1.0 is better)
  - `safety_score`: Average clearance from obstacles [0, 1]
  - `smoothness_score`: Heading stability [0, 1]
  - `outcome_quality`: Composite score [0, 1]

- **Outcome**:
  - `success_binary`: 1 if mission succeeded, 0 otherwise
  - `time_to_goal_s`: Time taken to reach goal
  - `composite_score`: Overall performance metric

---

## Workflow

### Initial Setup

```bash
# 1. Ensure episodic_memory symlink is set up
ls -la episodic_memory/  # Should show -> /path/to/slamo/episodic_memory

# 2. Generate initial fingerprints from existing episodes
python3 tools/add_fingerprints.py batch
# Creates etc/fingerprint_database.json with 58 episodes

# 3. Inspect the database
python3 tools/inspect_fingerprints.py stats
```

### Regular Use (When SLAMO Generates New Episodes)

The system can work two ways:

**Option A: Automatic (via main.py)**
```bash
# Start main.py to monitor for new episodes
python3 src/main.py

# It will:
# 1. Detect new episodes in episodic_memory/
# 2. Compute fingerprints automatically
# 3. Add to database (future: integrated)
# 4. Generate recommendations
```

**Option B: Manual (for testing)**
```bash
# After SLAMO creates a new episode manually:
python3 tools/add_fingerprints.py single episodic_memory/location/ep_NEW.json

# Or add multiple new episodes:
python3 tools/add_fingerprints.py batch --no-skip-existing
```

### Browsing Data

```bash
# Quick overview
python3 tools/inspect_fingerprints.py stats

# Find high-quality episodes
python3 tools/inspect_fingerprints.py search --quality 0.65

# Export for analysis
python3 tools/inspect_fingerprints.py export --output analysis.csv
```

---

## Future Enhancements

- [ ] Auto-detect new episodes and update database
- [ ] Visualization of fingerprints in 2D/3D space
- [ ] k-NN search visualization
- [ ] Parameter recommendation feedback loop
- [ ] Database versioning and rollback
- [ ] Query optimization for large databases
