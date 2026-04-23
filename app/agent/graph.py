from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.services.crawler import crawl_job_posting
from app.services.analyzer import extract_job_info
from app.services.matcher import match_resume_to_job
from app.services.cover_letter import generate_cover_letter


class AgentState(TypedDict):
    job_url: str
    resume_text: str
    job_content: str
    job_info: dict
    match_result: dict
    cover_letter: dict


def crawl_node(state: AgentState) -> AgentState:
    state["job_content"] = crawl_job_posting(state["job_url"])
    return state


def analyze_node(state: AgentState) -> AgentState:
    state["job_info"] = extract_job_info(state["job_content"])
    return state


def match_node(state: AgentState) -> AgentState:
    state["match_result"] = match_resume_to_job(
        state["resume_text"], state["job_info"]
    )
    return state


def cover_letter_node(state: AgentState) -> AgentState:
    state["cover_letter"] = generate_cover_letter(
        state["resume_text"], state["job_info"], state["match_result"]
    )
    return state


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("crawl", crawl_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("match", match_node)
    graph.add_node("cover_letter", cover_letter_node)

    graph.set_entry_point("crawl")
    graph.add_edge("crawl", "analyze")
    graph.add_edge("analyze", "match")
    graph.add_edge("match", "cover_letter")
    graph.add_edge("cover_letter", END)

    return graph.compile()