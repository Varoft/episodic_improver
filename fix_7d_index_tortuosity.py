#!/usr/bin/env python3
"""
fix_7d_index_tortuosity.py: Repara el bug de tortuosity=0 en el índice 7D
"""

import json
import math
from pathlib import Path

def safe_get(d, *keys, default=None):
    """Navega anidación en dicts de forma segura."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def recalculate_f5_and_f7(episode_path, f6):
    """
    Recalcula f5 (tortuosity) y f7 (complexity) desde los datos reales del episodio.
    
    f5 = distance_traveled_m / straight_line_distance
    f7 = f6 * f5
    """
    try:
        with open(episode_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"    ERROR leyendo {episode_path}: {e}")
        return 1.0, f6
    
    # Coordenadas
    src_x = float(safe_get(data, 'source', 'x', default=0))
    src_y = float(safe_get(data, 'source', 'y', default=0))
    tgt_x = float(safe_get(data, 'target', 'target_x', default=0))
    tgt_y = float(safe_get(data, 'target', 'target_y', default=0))
    
    # Distancia recta
    dx = tgt_x - src_x
    dy = tgt_y - src_y
    straight_dist = math.sqrt(dx**2 + dy**2)
    
    # Distancia viajada (REAL desde trajectory)
    distance_traveled = float(safe_get(data, 'trajectory', 'distance_traveled_m', default=straight_dist))
    
    # Tortuosity: relación entre distancia real y recta
    if straight_dist > 0.01:
        f5 = distance_traveled / straight_dist
    else:
        f5 = 1.0
    
    # Complejidad: densidad × tortuosity
    f7 = f6 * f5
    
    return f5, f7

def fix_index(index_path):
    """Lee el índice, recalcula f5 y f7 para cada episodio, guarda."""
    
    print(f"\n{'='*70}")
    print(f"REPARANDO ÍNDICE 7D: Tortuosity Bug Fix")
    print(f"{'='*70}\n")
    
    with open(index_path) as f:
        index = json.load(f)
    
    print(f"📁 Archivo: {index_path}")
    print(f"📊 Total items: {index['metadata']['total_items']}")
    
    fixed_count = 0
    all_fps = []
    
    for folder_name, episodes in index['folders'].items():
        print(f"\n📂 {folder_name}/ ({len(episodes)} episodios)")
        
        for i, episode in enumerate(episodes):
            # Construir ruta del episodio
            rel_path = episode['file']  # e.g., "ida/ep_1773933376465_1016942.json"
            episode_path = f"episodic_memory_7d_legacy/{folder_name}/{rel_path}"
            
            f6_original = episode['fingerprint_7d'][5]  # f6_density (sin cambios)
            f5_new, f7_new = recalculate_f5_and_f7(episode_path, f6_original)
            
            # Valores anteriores
            old_f5 = episode['fingerprint_7d'][4]
            old_f7 = episode['fingerprint_7d'][6]
            
            # Actualizar
            episode['fingerprint_7d'][4] = f5_new
            episode['fingerprint_7d'][6] = f7_new
            
            all_fps.append(episode['fingerprint_7d'])
            
            if old_f5 != f5_new:
                fixed_count += 1
                if i < 3:  # Show first 3 de cada carpeta
                    print(f"  ✓ {episode['episode_id']}")
                    print(f"    f5: {old_f5:.4f} → {f5_new:.4f}")
                    print(f"    f7: {old_f7:.4f} → {f7_new:.4f}")
        
        if len(episodes) > 3:
            print(f"  ... ({len(episodes) - 3} más)")
    
    print(f"\n{'='*70}")
    print(f"Recalculando means y stds globales...\n")
    
    # Recalcular means/stds globales (7D)
    dims = 7
    means_new = [0.0] * dims
    stds_new = [0.0] * dims
    
    if all_fps:
        n = len(all_fps)
        sums = [0.0] * dims
        sums2 = [0.0] * dims
        
        for fp in all_fps:
            for i in range(dims):
                v = fp[i]
                sums[i] += v
                sums2[i] += v * v
        
        means_new = [s / n for s in sums]
        stds_new = [math.sqrt(max(0.0, sums2[i] / n - means_new[i]**2)) for i in range(dims)]
    
    print("📈 Estadísticas ANTES (con bug):")
    print(f"   Means: {[f'{m:.6f}' for m in index['means']]}")
    print(f"   Stds:  {[f'{s:.6f}' for s in index['stds']]}")
    
    print("\n📈 Estadísticas DESPUÉS (reparado):")
    print(f"   Means: {[f'{m:.6f}' for m in means_new]}")
    print(f"   Stds:  {[f'{s:.6f}' for s in stds_new]}")
    
    print("\n✅ Cambios:")
    for i in range(dims):
        if means_new[i] != index['means'][i] or stds_new[i] != index['stds'][i]:
            desc = ['f1_pos_x', 'f2_pos_y', 'f3_heading', 'f4_distance', 'f5_tortuosity', 'f6_density', 'f7_complexity'][i]
            print(f"   {desc}:")
            print(f"     mean: {index['means'][i]:.6f} → {means_new[i]:.6f}")
            print(f"     std:  {index['stds'][i]:.6f} → {stds_new[i]:.6f}")
    
    # Actualizar index
    index['means'] = means_new
    index['stds'] = stds_new
    
    # Recalcular normalizaciones
    print(f"\n🔄 Normalizando fingerprints...")
    for folder_name, episodes in index['folders'].items():
        for ep in episodes:
            norm = []
            for i in range(dims):
                v = ep['fingerprint_7d'][i]
                std_val = stds_new[i] if stds_new[i] > 1e-8 else 1.0
                norm.append((v - means_new[i]) / std_val)
            ep['fingerprint_norm'] = norm
    
    # Guardar
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✅ REPARACIÓN COMPLETADA")
    print(f"{'='*70}")
    print(f"\n📊 Estadísticas finales:")
    print(f"   Episodios reparados: {fixed_count}")
    print(f"   Archivo guardado: {index_path}")
    print(f"   Estado: LISTO para usar\n")

if __name__ == '__main__':
    import sys
    
    # Default path
    index_file = 'episodic_memory_7d_legacy/fingerprints_index_unified_7d.json'
    
    if len(sys.argv) > 1:
        index_file = sys.argv[1]
    
    if not Path(index_file).exists():
        print(f"❌ ERROR: Archivo no encontrado: {index_file}")
        sys.exit(1)
    
    fix_index(index_file)
