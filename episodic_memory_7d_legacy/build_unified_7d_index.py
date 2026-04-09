#!/usr/bin/env python3
"""
Build unified 7D fingerprint index from all 5 episodic memory folders.

Elimina los antiguos índices 5D y genera un único JSON con todos los descriptores
organizados por carpeta, con estadísticas globales de normalización.

Uso:
  python3 build_unified_7d_index.py <episodic_memory_path>

Resultado:
  fingerprints_index_unified_7d.json
    ├── metadata
    ├── means: [7 valores] (desde todos los episodios)
    ├── stds: [7 valores] (desde todos los episodios)
    └── folders:
        ├── beta_final: [items...]
        ├── abajo_medio: [items...]
        ├── beta_inicio: [items...]
        ├── inicio_fin_pasillo: [items...]
        └── medio_arriba: [items...]
"""

import json
import math
import os
import sys
from typing import Dict, List, Tuple
from pathlib import Path


def safe_get(d: Dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def extract_fingerprint_7d(data: Dict) -> Tuple[List[float], float]:
    """Extract 7D fingerprint"""
    src_x = safe_get(data, 'source', 'x')
    src_y = safe_get(data, 'source', 'y')
    tgt_x = safe_get(data, 'target', 'target_x')
    tgt_y = safe_get(data, 'target', 'target_y')
    density = safe_get(data, 'source', 'obstacle_density', default=0.5)
    estimated_distance = safe_get(data, 'estimated_distance', default=0)
    
    if None in (src_x, src_y, tgt_x, tgt_y):
        raise ValueError('Faltan coordenadas source/target en JSON')
    
    src_x = float(src_x)
    src_y = float(src_y)
    tgt_x = float(tgt_x)
    tgt_y = float(tgt_y)
    density = float(density)
    estimated_distance = float(estimated_distance)
    
    # f1, f2: normalized start position
    f1 = src_x / 80.0
    f2 = src_y / 80.0
    
    # f3: heading angle
    dx = tgt_x - src_x
    dy = tgt_y - src_y
    angle_rad = math.atan2(dy, dx)
    f3 = angle_rad / math.pi
    
    # f4: straight-line distance
    straight_dist = math.sqrt(dx**2 + dy**2)
    max_diagonal = math.sqrt(80**2 + 80**2)
    f4 = straight_dist / max_diagonal
    
    # f5: tortuosity
    if straight_dist > 0.01:
        f5 = estimated_distance / straight_dist
    else:
        f5 = 1.0
    
    # f6: obstacle density
    f6 = density
    
    # f7: density × tortuosity
    f7 = density * f5
    
    fingerprint_7d = [f1, f2, f3, f4, f5, f6, f7]
    
    dist_traveled = safe_get(data, 'trajectory', 'distance_traveled_m', default=None)
    if dist_traveled is not None:
        dist_traveled = float(dist_traveled)
    
    return fingerprint_7d, dist_traveled


def find_episodes_in_folder(folder_path: str) -> List[Tuple[str, str]]:
    """Find all ep_*.json files in ida/ and vuelta/ subdirectories"""
    episodes = []
    
    for subdir in ['ida', 'vuelta']:
        subdir_path = os.path.join(folder_path, subdir)
        if os.path.isdir(subdir_path):
            for filename in os.listdir(subdir_path):
                if filename.startswith('ep_') and filename.endswith('.json'):
                    filepath = os.path.join(subdir_path, filename)
                    episodes.append((filepath, subdir))
    
    return sorted(episodes)


def build_unified_7d_index(episodic_memory_path: str, output_file: str):
    """Build unified 7D index from 5 folders"""
    
    # List of folders to process (excluding 'old' and 'scripts')
    folders_to_process = [
        'beta_final',
        'abajo_medio',
        'beta_inicio',
        'inicio_fin_pasillo',
        'medio_arriba'
    ]
    
    # Collect all fingerprints globally
    all_fingerprints_7d = []
    folders_data = {}
    
    print("=" * 60)
    print("Building 7D Unified Index")
    print("=" * 60)
    
    # Phase 1: Extract fingerprints from all folders
    total_items = 0
    for folder_name in folders_to_process:
        folder_path = os.path.join(episodic_memory_path, folder_name)
        
        if not os.path.isdir(folder_path):
            print(f"⚠ Carpeta no encontrada: {folder_path}")
            continue
        
        print(f"\nProcessando: {folder_name}/")
        episodes_list = find_episodes_in_folder(folder_path)
        items = []
        
        for filepath, subdir in episodes_list:
            try:
                with open(filepath, 'r') as f:
                    episode_data = json.load(f)
                
                fp_7d, dist_traveled = extract_fingerprint_7d(episode_data)
                all_fingerprints_7d.append(fp_7d)
                
                items.append({
                    'file': os.path.relpath(filepath, folder_path),
                    'abs_path': filepath,
                    'fingerprint_7d': fp_7d,
                    'distance_traveled_m': dist_traveled,
                    'episode_id': episode_data.get('episode_id'),
                    'category': subdir  # 'ida' o 'vuelta'
                })
            except Exception as e:
                print(f"  ⚠ Error en {filepath}: {e}", file=sys.stderr)
        
        folders_data[folder_name] = items
        total_items += len(items)
        print(f"  → {len(items)} episodios extraídos")
    
    print(f"\n{'=' * 60}")
    print(f"Total de episodios: {total_items}")
    print(f"{'=' * 60}\n")
    
    # Phase 2: Calculate global means and stds (7D)
    if all_fingerprints_7d:
        dims = 7
        sums = [0.0] * dims
        sums2 = [0.0] * dims
        n = len(all_fingerprints_7d)
        
        for fp in all_fingerprints_7d:
            for i in range(dims):
                v = fp[i]
                sums[i] += v
                sums2[i] += v * v
        
        means = [s / n for s in sums]
        stds = [math.sqrt(max(0.0, sums2[i] / n - means[i] * means[i])) for i in range(dims)]
    else:
        means = [0.0] * 7
        stds = [1.0] * 7
    
    print("Estadísticas globales (7D):")
    print(f"  Means: {[round(m, 4) for m in means]}")
    print(f"  Stds:  {[round(s, 4) for s in stds]}")
    
    # Phase 3: Normalize fingerprints and add to folders data
    print("\nNormalizando descriptores...")
    for folder_name in folders_data:
        for item in folders_data[folder_name]:
            norm = []
            for i in range(7):
                v = item['fingerprint_7d'][i]
                mu = means[i]
                sigma = stds[i]
                if sigma > 0:
                    norm.append((v - mu) / sigma)
                else:
                    norm.append(0.0)
            item['fingerprint_norm'] = norm
    
    # Phase 4: Build output structure
    output_data = {
        'metadata': {
            'format': '7D fingerprint (Claude recommendation)',
            'total_items': total_items,
            'folders_count': len(folders_data),
            'dimensions': 7,
            'dimension_names': ['f1_pos_x', 'f2_pos_y', 'f3_heading', 'f4_distance', 'f5_tortuosity', 'f6_density', 'f7_density_tortuosity']
        },
        'means': means,
        'stds': stds,
        'folders': folders_data
    }
    
    # Phase 5: Save unified index
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"\n✓ Índice unificado guardado: {output_file}")
    
    # Phase 6: Clean up old files
    print("\nLimpiando índices antiguos...")
    
    # Remove fingerprints_index_unified.json (old 5D version)
    old_unified = os.path.join(episodic_memory_path, 'fingerprints_index_unified.json')
    if os.path.exists(old_unified):
        os.remove(old_unified)
        print(f"  ✓ Eliminado: {old_unified}")
    
    # Remove per-folder fingerprints_index.json (old 5D versions)
    for folder_name in folders_to_process:
        old_index = os.path.join(episodic_memory_path, folder_name, 'fingerprints_index.json')
        if os.path.exists(old_index):
            os.remove(old_index)
            print(f"  ✓ Eliminado: {old_index}")
    
    # Remove merge_indices.py (no longer needed)
    merge_script = os.path.join(episodic_memory_path, 'merge_indices.py')
    if os.path.exists(merge_script):
        os.remove(merge_script)
        print(f"  ✓ Eliminado: {merge_script}")
    
    print(f"\n{'=' * 60}")
    print("¡Listo! Índice 7D unificado generado.")
    print(f"{'=' * 60}\n")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    
    episodic_memory_path = argv[1]
    
    if not os.path.isdir(episodic_memory_path):
        print(f"Error: {episodic_memory_path} no es un directorio válido")
        return 1
    
    output_file = os.path.join(episodic_memory_path, 'fingerprints_index_unified_7d.json')
    build_unified_7d_index(episodic_memory_path, output_file)
    
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
