from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import mapping, shape as geom_from_json

from ..scoring import annotate_green

TAGS = {
    "leisure": ["park", "garden", "nature_reserve"],
    "natural": ["wood", "scrub", "grassland"],
    "landuse": ["grass", "forest", "recreation_ground"],
}
DIST = 1500
CACHE_DIR = Path("data/cache")


def _cache_key(lat: float, lon: float) -> str:
    return f"{lat:.3f}_{lon:.3f}"


def _open_green(path: str | Path) -> tuple[list, list]:
    """Returns (names, geometries) for the cached green features (no GDAL needed)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = [f.get("properties", {}).get("name") for f in data["features"]]
    geoms = [geom_from_json(f["geometry"]) for f in data["features"]]
    return names, geoms


def _place_names(names: list) -> list[str]:
    out = set()
    for n in names:
        if isinstance(n, str) and n.strip():
            out.add(n.strip())
    return sorted(out)


def save_green(path: str | Path, geoms: list, names: list | None = None) -> None:
    """Write green features as GeoJSON via shapely only."""
    names = names or [None] * len(geoms)
    features = [
        {"type": "Feature", "properties": {"name": n}, "geometry": mapping(g)}
        for n, g in zip(names, geoms)
    ]
    Path(path).write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )


def load_green(path: str | Path) -> list:
    """Load the cached green geometries for plotting."""
    _names, geoms = _open_green(path)
    return geoms


def load_graph(path: str | Path) -> nx.MultiDiGraph:
    """Load a cached projected graph and coerce OSMnx's stringified attributes."""
    G = ox.load_graphml(path)
    for _u, _v, _k, d in G.edges(keys=True, data=True):
        if isinstance(d.get("green"), str):
            try:
                d["green"] = float(d["green"])
            except ValueError:
                d["green"] = 0.0
    _restore_latlon(G)
    return G


def _restore_latlon(G) -> None:
    """OSMnx drops lat/lon when it serializes a projected graph, so inverse-project x/y."""
    crs = G.graph.get("crs")
    if not crs:
        return
    try:
        back = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    except Exception:
        return
    for _n, nd in G.nodes(data=True):
        if nd.get("lat") is None and nd.get("x") is not None:
            lon, lat = back.transform(nd["x"], nd["y"])
            nd["lat"], nd["lon"] = lat, lon


def _start_node(G, lat: float, lon: float) -> int:
    transformer = Transformer.from_crs("EPSG:4326", G.graph["crs"], always_xy=True)
    x, y = transformer.transform(lon, lat)
    return int(ox.distance.nearest_nodes(G, x, y))


def _green_features(G, feats):
    feats = feats.to_crs(G.graph["crs"])
    feats = feats[feats.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if not feats.empty:
        annotate_green(G, list(feats.geometry))
    return feats


def _download(state, key: str):
    pt = (state["start_lat"], state["start_lon"])
    G = ox.graph_from_point(pt, dist=DIST, network_type="walk")
    G = ox.project_graph(G)
    feats = _green_features(G, ox.features_from_point(pt, tags=TAGS, dist=DIST))
    gpath = CACHE_DIR / f"{key}.graphml"
    fpath = CACHE_DIR / f"{key}_green.geojson"
    ox.save_graphml(G, gpath)
    names = [n if isinstance(n, str) else None for n in feats.get("name")]
    save_green(fpath, list(feats.geometry), names)
    return G, names


def run(state):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(state["start_lat"], state["start_lon"])
    gpath = CACHE_DIR / f"{key}.graphml"
    fpath = CACHE_DIR / f"{key}_green.geojson"
    from_cache = gpath.exists() and fpath.exists()
    if from_cache:
        G = load_graph(gpath)
        names, _geoms = _open_green(fpath)
        warning = f"map_fetch: loaded map for {key} from cache"
    else:
        G, names = _download(state, key)
        warning = f"map_fetch: downloaded and cached map for {key}"
    return {
        "graph_path": str(gpath),
        "green_path": str(fpath),
        "place_names": _place_names(names),
        "start_node": _start_node(G, state["start_lat"], state["start_lon"]),
        "warnings": [warning],
    }