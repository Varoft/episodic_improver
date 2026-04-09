#!/usr/bin/env python3
"""
Genera huellas (fingerprints) 7D a partir de episodios JSON y permite buscar los 3 vecinos más cercanos.

Uso:
  python3 scripts/episodic_index.py build <base_folder>
  python3 scripts/episodic_index.py query <index_file> <episode_json>

Fingerprint 7D según recomendación de Claude (chat.txt):
  f1, f2: normalized start position (÷80)
  f3: heading angle (start→end), normalized a [-1,1]
  f4: straight-line distance (÷56.57m)
  f5: tortuosity (estimated_distance / straight_line_distance)
  f6: obstacle density
  f7: density × tortuosity
"""
import json
import math
import os
import sys
from typing import Dict, List, Tuple


def find_json_files(base: str) -> List[str]:
    out = []
    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith('.json'):
                out.append(os.path.join(root, f))
    return sorted(out)


def safe_get(d: Dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def extract_fingerprint_7d(data: Dict) -> Tuple[List[float], float]:
    """
    Extract 7-dimensional fingerprint based on Claude's recommendation.
    Also returns distance_traveled_m if available.
    """
    src_x = safe_get(data, 'source', 'x')
    src_y = safe_get(data, 'source', 'y')
    tgt_x = safe_get(data, 'target', 'target_x')
    tgt_y = safe_get(data, 'target', 'target_y')
    density = safe_get(data, 'source', 'obstacle_density', default=0.5)
    estimated_distance = safe_get(data, 'estimated_distance', default=0)
    
    # Check coordinates
    if None in (src_x, src_y, tgt_x, tgt_y):
        raise ValueError('Faltan coordenadas source/target en JSON')
    
    src_x = float(src_x)
    src_y = float(src_y)
    tgt_x = float(tgt_x)
    tgt_y = float(tgt_y)
    density = float(density)
    estimated_distance = float(estimated_distance)
    
    # f1, f2: normalized start position (divide by 80 = max coordinate range)
    f1 = src_x / 80.0
    f2 = src_y / 80.0
    
    # f3: heading angle normalized to [-1, 1]
    dx = tgt_x - src_x
    dy = tgt_y - src_y
    angle_rad = math.atan2(dy, dx)  # [-π, π]
    f3 = angle_rad / math.pi  # [-1, 1]
    
    # f4: straight-line distance (divide by max diagonal 113.14m)
    straight_dist = math.sqrt(dx**2 + dy**2)
    max_diagonal = math.sqrt(80**2 + 80**2)  # 113.14
    f4 = straight_dist / max_diagonal
    
    # f5: tortuosity (estimated_distance / straight_line_distance)
    if straight_dist > 0.01:
        f5 = estimated_distance / straight_dist
    else:
        f5 = 1.0
    
    # f6: obstacle density (already normalized 0-1)
    f6 = density
    
    # f7: density × tortuosity
    f7 = density * f5
    
    fingerprint_7d = [f1, f2, f3, f4, f5, f6, f7]
    
    # distance traveled if available
    dist_traveled = safe_get(data, 'trajectory', 'distance_traveled_m', default=None)
    if dist_traveled is not None:
        dist_traveled = float(dist_traveled)
    
    return fingerprint_7d, dist_traveled


def build_index(base_folder: str, out_file: str):
    """Build 7D fingerprint index and eliminate old file"""
    # Remove old index file if exists
    if os.path.exists(out_file):
        print(f"Eliminando índice anterior: {out_file}")
        os.remove(out_file)
    
    files = find_json_files(base_folder)
    index = []
    
    for fn in files:
        try:
            with open(fn, 'r') as f:
                j = json.load(f)
            fp_7d, dist_traveled = extract_fingerprint_7d(j)
            index.append({
                'file': os.path.relpath(fn, base_folder),
                'abs_path': fn,
                'fingerprint_7d': fp_7d,  # 7D fingerprint (raw)
                'distance_traveled_m': dist_traveled,
                'episode_id': j.get('episode_id')
            })
        except Exception as e:
            print(f"Skipping {fn}: {e}", file=sys.stderr)
    
    # Build per-dimension mean/std for 7D fingerprint normalization (z-score)
    if index:
        dims = 7  # Now always 7 dimensions
        sums = [0.0] * dims
        sums2 = [0.0] * dims
        n = len(index)
        
        for it in index:
            for i in range(dims):
                v = it['fingerprint_7d'][i]
                sums[i] += v
                sums2[i] += v * v

        means = [s / n for s in sums]
        stds = [math.sqrt(max(0.0, sums2[i] / n - means[i] * means[i])) for i in range(dims)]

        # compute normalized fingerprint for each item (z = (v-mean)/std)
        for it in index:
            norm = []
            for i in range(dims):
                v = it['fingerprint_7d'][i]
                mu = means[i]
                sigma = stds[i]
                if sigma > 0:
                    norm.append((v - mu) / sigma)
                else:
                    norm.append(0.0)
            it['fingerprint_norm'] = norm
    else:
        means = []
        stds = []

    with open(out_file, 'w') as f:
        json.dump({
            'base': base_folder,
            'episodes': index,  # Renamed from 'items' for clarity
            'means': means,
            'stds': stds
        }, f, indent=2)
    
    print(f'✓ Índice 7D generado: {out_file} ({len(index)} items)')
    if index:
        print(f'  Dimensiones: 7')
        print(f'  Means: {[round(m, 4) for m in means]}')
        print(f'  Stds:  {[round(s, 4) for s in stds]}')


def euclid(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def query_index(index_file: str, episode_file: str, k: int = 3):
    """Query k-nearest neighbors using 7D fingerprint"""
    with open(index_file, 'r') as f:
        idx = json.load(f)
    base = idx.get('base', '.')
    items = idx.get('episodes', idx.get('items', []))  # Support both keys

    with open(episode_file, 'r') as f:
        qj = json.load(f)
    qfp, qdist = extract_fingerprint_7d(qj)
    
    # normalize query fingerprint using means/stds from index
    means = idx.get('means', [])
    stds = idx.get('stds', [])
    qnorm = []
    if means and stds:
        for i, v in enumerate(qfp):
            mu = means[i]
            sigma = stds[i]
            if sigma > 0:
                qnorm.append((v - mu) / sigma)
            else:
                qnorm.append(0.0)
    else:
        qnorm = qfp

    # compute distances on raw (unnormalized) fingerprints
    dists = []
    for it in items:
        try:
            stored_fp = it.get('fingerprint_7d', it.get('fingerprint'))
            if len(stored_fp) != len(qfp):
                continue
            dist = euclid(qfp, stored_fp)
            dists.append((dist, it))
        except Exception:
            continue

    dists.sort(key=lambda x: x[0])
    nearest = dists[:k]

    # print results
    print(f'Query: {episode_file}')
    print(f'  fingerprint_7d (raw): {[round(x, 4) for x in qfp]}')
    print(f'  fingerprint_7d (norm): {[round(x, 4) for x in qnorm]}')
    print(f'\nVecinos más cercanos (k={k}):')
    for dist, it in nearest:
        print(f"- {it['file']} (euclid={dist:.4f}) distance_traveled_m={it.get('distance_traveled_m')}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == 'build':
        if len(argv) < 3:
            print('Usage: build <base_folder>')
            return 1
        base = argv[2]
        out = os.path.join(base, 'fingerprints_index.json')
        build_index(base, out)
        return 0
    elif cmd == 'query':
        if len(argv) < 4:
            print('Usage: query <index_file> <episode_json>')
            return 1
        query_index(argv[2], argv[3])
        return 0
    else:
        print('Unknown command', cmd)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
