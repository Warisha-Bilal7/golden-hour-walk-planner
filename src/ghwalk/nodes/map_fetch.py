from __future__ import annotations


def run(state):
    return {
        "graph_path": "data/cache/stub.graphml",
        "green_path": "data/cache/stub_green.geojson",
        "place_names": ["Stub Park", "Riverside Path", "Central Green"],
        "start_node": 0,
        "warnings": ["map_fetch: stub, no OSM download"],
    }
