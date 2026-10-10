import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


class IntakeParams(BaseModel):
    duration_min: int = Field(default=45, ge=15, le=120)
    preferences: list[str] = Field(default_factory=list)
    pace: Literal["slow", "normal", "brisk"] = "normal"


class RouteParams(TypedDict):
    target_m: float
    tolerance: float
    max_overlap: float
    w_green: float
    n_candidates: int
    radius_factor: float


class Candidate(TypedDict):
    nodes: list[int]
    length_m: float
    green_pct: float
    overlap_pct: float
    score: float


class CriticResult(TypedDict):
    passed: bool
    reasons: list[str]


class WalkState(TypedDict, total=False):
    # inputs
    user_request: str
    start_lat: float
    start_lon: float
    tz: str
    model_name: str

    # intake
    intake: dict
    speed_kmh: float

    # sun
    sunset_iso: str
    golden_start_iso: str
    walk_start_iso: str
    walk_end_iso: str
    light_bearing_deg: float

    # weather
    weather: dict

    # map
    graph_path: str
    green_path: str
    place_names: list[str]
    start_node: int

    # routing
    params: RouteParams
    candidates: list[Candidate]
    best: Candidate | None
    attempt: int
    critic: CriticResult

    # outputs
    card_text: str
    used_fallback: bool
    pdf_path: str
    gpx_path: str
    route_map_path: str

    warnings: Annotated[list[str], operator.add]


def initial_state(
    user_request: str,
    start_lat: float,
    start_lon: float,
    tz: str = "UTC",
    model_name: str = "qwen2.5:3b",
) -> WalkState:
    return {
        "user_request": user_request,
        "start_lat": start_lat,
        "start_lon": start_lon,
        "tz": tz,
        "model_name": model_name,
        "attempt": 0,
        "warnings": [],
    }
