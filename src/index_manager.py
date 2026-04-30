"""
IndexManager: Gestor del indice de fingerprints con busqueda K-NN.
Responsable de: cargar, normalizar y buscar episodios similares.
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Optional


class IndexManager:
    """
    Gestor del indice de fingerprints.

    Funcionalidades:
    - Cargar indice desde JSON
    - Normalizar descriptores usando means/stds
    - Buscar K-NN con metrica de distancia ponderada
    - Gestionar cache de busquedas
    """

    def __init__(self, index_path: str, weights: Optional[List[float]] = None):
        """
        Inicializa el gestor del indice.

        Args:
            index_path: Ruta al index.json
            weights: Pesos para distancia: [w_f1, w_f2, ..., w_f7]
                     Si es None, usa valores por defecto
        """
        self.index_path = Path(index_path)
        self.index_data = None
        self.episodes_flat = []
        self.metadata = {}
        self.base_dir = self.index_path.parent

        self.weights = weights or [
            0.8,  # f1_pos_x
            0.8,  # f2_pos_y
            0.6,  # f3_heading
            1.2,  # f4_distance
            1.0,  # f5_tortuosity
            1.1,  # f6_density
            1.0   # f7_density_tortuosity
        ]

        self._load_index()

    def _load_index(self) -> None:
        """Carga el indice desde JSON."""
        if not self.index_path.exists():
            raise FileNotFoundError(f"Indice no encontrado: {self.index_path}")

        try:
            with open(self.index_path, "r") as f:
                self.index_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al parsear JSON: {e}")

        self.metadata = self.index_data.get("metadata", {})
        base_path = self.index_data.get("base")
        if base_path:
            base_path_obj = Path(base_path)
            self.base_dir = (self.index_path.parent / base_path_obj).resolve()
        means = self.index_data.get("means", [0.0] * 7)
        stds = self.index_data.get("stds", [1.0] * 7)

        self.means = means
        self.stds = [s if s > 0.0001 else 1.0 for s in stds]

        total_items = self.metadata.get("total_items", 0)
        print(f"Index loaded: {total_items} episodes")
        print(f"  Means: {self.means}")
        print(f"  Stds:  {self.stds}")

        self._build_flat_episodes_list()

    def _build_flat_episodes_list(self) -> None:
        """Convierte la estructura del indice a una lista plana."""
        self.episodes_flat = []
        folders = self.index_data.get("folders", {})

        for folder_name, episodes_list in folders.items():
            for ep in episodes_list:
                ep["folder"] = folder_name
                self.episodes_flat.append(ep)

        print(f"Flat list built: {len(self.episodes_flat)} episodes indexed")

    def save_index(self, output_path: Optional[str] = None) -> None:
        """Guarda el indice actualizado a disco."""
        target_path = Path(output_path) if output_path else self.index_path
        with open(target_path, "w") as f:
            json.dump(self.index_data, f, indent=2)

    def get_episode_record(self, episode_id: str) -> Optional[Dict]:
        """Devuelve el registro del indice para un episodio especifico."""
        for ep in self.episodes_flat:
            if ep.get("episode_id") == episode_id:
                return ep
        return None

    def get_episode_file_path(self, episode_id: str) -> Optional[Path]:
        """Obtiene la ruta al archivo JSON de un episodio desde el indice."""
        ep = self.get_episode_record(episode_id)
        if not ep:
            return None

        base_dir = self.base_dir
        abs_path = ep.get("abs_path")
        rel_path = ep.get("file")

        if abs_path:
            abs_path_obj = Path(abs_path)
            if abs_path_obj.is_absolute():
                return abs_path_obj
            return (base_dir / abs_path_obj).resolve()
        if rel_path:
            return (base_dir / rel_path).resolve()

        return None

    def set_base_dir(self, base_dir: Path) -> None:
        """Define la carpeta base para resolver rutas del indice."""
        self.base_dir = base_dir

    def load_episode_json(self, episode_id: str) -> Optional[Dict]:
        """Carga el JSON del episodio desde el path almacenado en el indice."""
        episode_path = self.get_episode_file_path(episode_id)
        if not episode_path:
            return None

        try:
            with open(episode_path, "r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def add_episode_entry(
        self,
        episode_data: Dict,
        episode_path: Path,
        folder_name: str = "runtime",
        category: str = "unknown"
    ) -> None:
        """Agrega un episodio nuevo al indice y actualiza la lista plana."""
        self.metadata = self.index_data.setdefault("metadata", self.metadata or {})
        fp = episode_data.get("fingerprint")
        if not fp or len(fp) != 7:
            raise ValueError("fingerprint invalido o ausente")

        fp_norm = self.normalize_fingerprint(fp)
        try:
            rel_path = episode_path.relative_to(self.index_path.parent)
        except ValueError:
            rel_path = episode_path

        entry = {
            "file": str(rel_path),
            "abs_path": str(episode_path.resolve()),
            "fingerprint": fp,
            "distance_traveled_m": episode_data.get("distance_traveled_m"),
            "episode_id": episode_data.get("episode_id"),
            "category": category,
            "fingerprint_norm": fp_norm,
            "params_snapshot": episode_data.get("params_snapshot", {}),
            "outcome": episode_data.get("outcome", {})
        }

        folders = self.index_data.setdefault("folders", {})
        folders.setdefault(folder_name, []).append(entry)

        total_items = self.metadata.get("total_items", 0)
        self.metadata["total_items"] = total_items + 1

        self._build_flat_episodes_list()

    def normalize_fingerprint(self, fp_raw: List[float]) -> List[float]:
        """
        Normaliza un fingerprint usando means/stds del indice.

        Formula: fp_norm = (fp_raw - mean) / std
        """
        if len(fp_raw) != 7:
            raise ValueError(f"Fingerprint debe tener 7 elementos, recibido {len(fp_raw)}")

        fp_norm = []
        for i in range(7):
            if self.stds[i] > 0.0001:
                fp_norm.append((fp_raw[i] - self.means[i]) / self.stds[i])
            else:
                fp_norm.append(fp_raw[i])

        return fp_norm

    def weighted_distance(self, fp_norm_query: List[float], fp_norm_episode: List[float]) -> float:
        """
        Calcula distancia ponderada entre dos fingerprints normalizados.

        Formula: dist = sqrt(sum((w_i * (fp_query_i - fp_episode_i))^2))
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
        Busca los K episodios mas similares a una mision nueva.

        Returns:
            Lista de dicts con:
            - episode_id
            - folder
            - category
            - fingerprint
            - distance_traveled_m
            - similarity_score
            - weighted_distance
        """
        if k < 1:
            raise ValueError("k debe ser >= 1")

        fp_norm_query = self.normalize_fingerprint(fp_raw_query)

        distances = []
        for ep in self.episodes_flat:
            fp_norm_ep = ep.get("fingerprint_norm", [])
            if not fp_norm_ep:
                continue

            dist = self.weighted_distance(fp_norm_query, fp_norm_ep)
            distances.append({
                "episode": ep,
                "distance": dist
            })

        if not distances:
            return []

        distances.sort(key=lambda x: x["distance"])
        top_k = distances[:k]

        results = []
        max_distance = distances[-1]["distance"] if distances else 1.0

        for i, item in enumerate(top_k):
            ep = item["episode"]
            dist = item["distance"]

            similarity = 1.0 - (dist / (max_distance + 0.001))

            results.append({
                "rank": i + 1,
                "episode_id": ep.get("episode_id"),
                "folder": ep.get("folder"),
                "category": ep.get("category"),
                "fingerprint": ep.get("fingerprint"),
                "distance_traveled_m": ep.get("distance_traveled_m"),
                "weighted_distance": dist,
                "similarity_score": similarity,
                "composite_score": (ep.get("outcome") or {}).get("composite_score")
            })

        return results

    def get_episode_params(self, episode_id: str) -> Optional[Dict]:
        """Obtiene los parametros almacenados de un episodio especifico."""
        for ep in self.episodes_flat:
            if ep.get("episode_id") == episode_id:
                return ep.get("params_snapshot", {})
        return None

    def get_episode_outcome(self, episode_id: str) -> Optional[Dict]:
        """Obtiene los scores/outcome de un episodio especifico."""
        for ep in self.episodes_flat:
            if ep.get("episode_id") == episode_id:
                return ep.get("outcome", {})
        return None

    def update_weights(self, new_weights: List[float]) -> None:
        """Actualiza los pesos de la metrica de distancia."""
        if len(new_weights) != 7:
            raise ValueError("Deben ser exactamente 7 pesos")
        if any(w <= 0 for w in new_weights):
            raise ValueError("Todos los pesos deben ser positivos")

        self.weights = new_weights
        print(f"Weights updated: {self.weights}")
