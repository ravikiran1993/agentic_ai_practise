from __future__ import annotations

from typing import Any

from startup_radar.models import RetrievedEvidence


def create_chat_turn(
    question: str,
    answer: str,
    evidence: list[RetrievedEvidence],
    mode: str,
) -> dict[str, Any]:
    """Create a serializable chat turn for Streamlit session state."""
    return {
        "question": question,
        "answer": answer,
        "evidence": evidence,
        "mode": mode,
    }


def append_chat_turn(history: list[dict[str, Any]], turn: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a new chat history with the turn appended."""
    return [*history, turn]
