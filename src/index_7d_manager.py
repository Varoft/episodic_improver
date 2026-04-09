"""
Index7DManager: Gestor del índice 7D con búsqueda K-NN
Responsable de: cargar, normalizar y buscar episodios similares
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class Index7DManager:
    """
    Gestor del índice de fingerprints 7D.
    
    Funcionalidades:
    - Cargar índice desde JSON
    - Normalizar descriptores usando means/stds
    - Buscar K-NN con métrica de distancia ponderada
    - Gestionar caché de búsquedas
    """
    
    def __init__(self, index_path: str, weights: Optional[List[float]] = None):
        """
        Inicializa el gestor del índice.
        
        Args:
            index_path: Ruta a fingerprints_index_unified_7d.json
            weights: Pesos para distancia: [w_f1, w_f2, ..., w_f7]
                     Si es None, usa valores por defecto
        """
        self.index_path = Path(index_path)
        self.index_data = None
        self.episodes_flat = []  # Lista plana para búsqueda
        self.metadata = {}
        
        # Pesos por defecto (usuario configurable)
        self.weights = weights or [
            0.8,   # f1_pos_x (posición importante)
            0.8,   # f2_pos_y
            0.6,   # f3_heading (menos crítico)
            1.2,   # f4_distance (distancia importante)
            1.0,   # f5_tortuosity
            1.1,   # f6_density (obstáculos muy importantes)
            1.0    # f7_complexity
        ]
        
        self._load_index()
    
    def _load_index(self) -> None:
        """Carga el índice desde JSON."""
        if not self.index_path.exists():
            raise FileNotFoundError(f"Índice no encontrado: {self.index_path}")
        
        try:
            with open(self.index_path, 'r') as f:
                self.index_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al parsear JSON: {e}")
        
        # Extraer metadata (está en raíz, no dentro de metadata)
        self.metadata = self.index_data.get('metadata', {})
        means = self.index_data.get('means', [0.0] * 7)
        stds = self.index_data.get('stds', [1.0] * 7)
        
        # Validar que means y stds son válidos (evitar división por cero)
        self.means = means
        self.stds = [s if s > 0.0001 else 1.0 for s in stds]
        
        total_items = self.metadata.get('total_items', 0)
        print(f"✓ Índice cargado: {total_items} episodios")
        print(f"  Means: {self.means}")
        print(f"  Stds:  {self.stds}")
        
        # Construir lista plana de episodios
        self._build_flat_episodes_list()
    
    def _build_flat_episodes_list(self) -> None:
        """Convierte la estructura del índice a una lista plana."""
        self.episodes_flat = []
        folders = self.index_data.get('folders', {})
        
        for folder_name, episodes_list in folders.items():
            # folders[folder_name] es una lista de episodios
            for ep in episodes_list:
                ep['folder'] = folder_name
                # 'category' en el JSON corresponde a ida/vuelta
                self.episodes_flat.append(ep)
        
        print(f"✓ Lista plana construida: {len(self.episodes_flat)} episodios indexados")
    
    def normalize_fingerprint(self, fp_raw: List[float]) -> List[float]:
        """
        Normaliza un fingerprint usando means/stds del índice.
        
        Formula: fp_norm = (fp_raw - mean) / std
        
        Args:
            fp_raw: [f1_raw, f2_raw, ..., f7_raw]
            
        Returns:
            [f1_norm, f2_norm, ..., f7_norm]
        """
        if len(fp_raw) != 7:
            raise ValueError(f"Fingerprint debe tener 7 elementos, recibido {len(fp_raw)}")
        
        fp_norm = []
        for i in range(7):
            if self.stds[i] > 0.0001:
                fp_norm.append((fp_raw[i] - self.means[i]) / self.stds[i])
            else:
                # Si std es 0 (como en f5/f7 antes del bug fix), devolver el valor crudo
                fp_norm.append(fp_raw[i])
        
        return fp_norm
    
    def weighted_distance(self, fp_norm_query: List[float], 
                         fp_norm_episode: List[float]) -> float:
        """
        Calcula distancia ponderada entre dos fingerprints normalizados.
        
        Formula: dist = sqrt(sum((w_i * (fp_query_i - fp_episode_i))^2))
        
        Args:
            fp_norm_query: Fingerprint normalizado de la nueva misión
            fp_norm_episode: Fingerprint normalizado de un episodio histórico
            
        Returns:
            Distancia ponderada (menores valores = más similares)
        """
        if len(fp_norm_query) != 7 or len(fp_norm_episode) != 7:
            raise ValueError("Ambos fingerprints deben tener 7 elementos")
        
        sum_weighted_sq = 0.0
        for i in range(7):
            diff = fp_norm_query[i] - fp_norm_episode[i]
            sum_weighted_sq += (self.weights[i] * diff) ** 2
        
        return math.sqrt(sum_weighted_sq)
    
    def search_knn(self, fp_raw_query: List[float], k: int = 3) -> List[Dict]:
        """
        Busca los K episodios más similares a una misión nueva.
        
        Args:
            fp_raw_query: Fingerprint 7D crudo de la nueva misión
            k: Número de resultados a retornar
            
        Returns:
            Lista de K dicts con:
            - 'episode_id': ID del episodio
            - 'location': ubicación (ej: 'beta_final')
            - 'direction': 'ida' o 'vuelta'
            - 'fingerprint_7d': vector 7D crudo
            - 'fingerprint_norm': vector 7D normalizado
            - 'distance_traveled_m': distancia recorrida
            - 'similarity_score': 1.0 - distancia_normalizada
            - 'weighted_distance': distancia ponderada
        """
        if k < 1:
            raise ValueError("k debe ser >= 1")
        
        # Normalizar fingerprint de la query
        fp_norm_query = self.normalize_fingerprint(fp_raw_query)
        
        # Calcular distancia a todos los episodios
        distances = []
        for ep in self.episodes_flat:
            fp_norm_ep = ep.get('fingerprint_norm', [])
            if not fp_norm_ep:
                continue
            
            dist = self.weighted_distance(fp_norm_query, fp_norm_ep)
            distances.append({
                'episode': ep,
                'distance': dist
            })
        
        # Ordenar por distancia y tomar top K
        distances.sort(key=lambda x: x['distance'])
        top_k = distances[:k]
        
        # Construir resultado con información extra
        results = []
        max_distance = distances[-1]['distance'] if distances else 1.0
        
        for i, item in enumerate(top_k):
            ep = item['episode']
            dist = item['distance']
            
            # Similarity score normalizado a [0, 1]: 1 = igual, 0 = muy diferente
            similarity = 1.0 - (dist / (max_distance + 0.001))
            
            results.append({
                'rank': i + 1,
                'episode_id': ep.get('episode_id'),
                'folder': ep.get('folder'),
                'category': ep.get('category'),  # 'ida' o 'vuelta'
                'fingerprint_7d': ep.get('fingerprint_7d'),
                'distance_traveled_m': ep.get('distance_traveled_m'),
                'weighted_distance': dist,
                'similarity_score': similarity
            })
        
        return results
    
    def get_episode_params(self, episode_id: str) -> Optional[Dict]:
        """
        Obtiene los parámetros almacenados de un episodio específico.
        
        Args:
            episode_id: ID del episodio (ej: 'ep_1773933376465_1016942')
            
        Returns:
            Dict con los 27 parámetros del episodio, o None si no existe
        """
        for ep in self.episodes_flat:
            if ep.get('episode_id') == episode_id:
                return ep.get('params_snapshot', {})
        return None
    
    def get_episode_outcome(self, episode_id: str) -> Optional[Dict]:
        """
        Obtiene los scores/outcome de un episodio específico.
        
        Args:
            episode_id: ID del episodio
            
        Returns:
            Dict con los 4 scores (composite, efficiency, safety, comfort), o None
        """
        for ep in self.episodes_flat:
            if ep.get('episode_id') == episode_id:
                return ep.get('outcome', {})
        return None
    
    def update_weights(self, new_weights: List[float]) -> None:
        """
        Actualiza los pesos de la métrica de distancia.
        
        Args:
            new_weights: Lista de 7 flotantes positivos
        """
        if len(new_weights) != 7:
            raise ValueError("Deben ser exactamente 7 pesos")
        if any(w <= 0 for w in new_weights):
            raise ValueError("Todos los pesos deben ser positivos")
        
        self.weights = new_weights
        print(f"✓ Pesos actualizados: {self.weights}")


# ============================================================================
# PRUEBAS
# ============================================================================

if __name__ == "__main__":
    # Prueba básica de carga
    index_path = "/home/usuario/episodic_improver/episodic_memory_7d_legacy/fingerprints_index_unified_7d.json"
    
    print("=" * 70)
    print("PRUEBA: Index7DManager")
    print("=" * 70)
    
    try:
        manager = Index7DManager(index_path)
        
        # Fingerprint de prueba (valores normalizados entre -1 y 1)
        fp_test = [0.05, -0.1, 0.2, 0.3, 1.0, 0.5, 0.5]
        
        print(f"\n▶ Búsqueda K-NN para fp_test = {fp_test}")
        results = manager.search_knn(fp_test, k=3)
        
        for result in results:
            print(f"\n  [{result['rank']}] {result['episode_id']}")
            print(f"      Ubicación: {result['folder']}/{result['category']}")
            print(f"      Distancia ponderada: {result['weighted_distance']:.4f}")
            print(f"      Similitud: {result['similarity_score']:.2%}")
        
        # Obtener params del mejor
        best_ep_id = results[0]['episode_id']
        params = manager.get_episode_params(best_ep_id)
        print(f"\n▶ Parámetros del mejor match ({best_ep_id}):")
        if params:
            print(f"   (Total: {len(params)} parámetros, primeros 3:)")
            for pname, pvalue in list(params.items())[:3]:
                print(f"   {pname}: {pvalue}")
        else:
            print("   (No hay params en el índice - están en archivos individuales)")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
