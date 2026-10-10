from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from .nodes import (
    card_writer,
    critic,
    intake,
    map_fetch,
    render,
    route_builder,
    sun,
    weather,
)
from .state import WalkState

MAX_ATTEMPTS = 3


def critic_router(state: WalkState) -> Literal["route_builder", "card_writer", "give_up"]:
    if state["critic"]["passed"]:
        return "card_writer"
    if state["attempt"] >= MAX_ATTEMPTS:
        return "card_writer" if state.get("best") else "give_up"
    return "route_builder"


def build_graph():
    g = StateGraph(WalkState)
    g.add_node("intake", intake.run)
    g.add_node("sun", sun.run)
    g.add_node("weather", weather.run)
    g.add_node("map_fetch", map_fetch.run)
    g.add_node("route_builder", route_builder.run)
    g.add_node("critic", critic.run)
    g.add_node("card_writer", card_writer.run)
    g.add_node("render", render.run)

    g.add_edge(START, "intake")
    g.add_edge("intake", "sun")
    g.add_edge("sun", "weather")
    g.add_edge("weather", "map_fetch")
    g.add_edge("map_fetch", "route_builder")
    g.add_edge("route_builder", "critic")
    g.add_conditional_edges(
        "critic",
        critic_router,
        {"route_builder": "route_builder", "card_writer": "card_writer", "give_up": END},
    )
    g.add_edge("card_writer", "render")
    g.add_edge("render", END)
    return g.compile()
