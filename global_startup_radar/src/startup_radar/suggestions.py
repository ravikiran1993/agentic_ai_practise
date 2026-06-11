from __future__ import annotations


def get_suggested_questions() -> list[str]:
    """Return demo-ready startup trend questions for the app."""
    return [
        "Which startups are trending right now and what evidence supports them?",
        "What themes are emerging from the latest Product Hunt launches?",
        "Compare the top five startups by traction signals and product positioning.",
        "Which AI-related startups have the strongest traction signals?",
        "Which startups have the clearest product positioning?",
        "Which startups have weak evidence or lower confidence?",
        "Summarize the main sectors represented in the current startup data.",
    ]
