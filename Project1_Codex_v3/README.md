# FAOSTAT Crop Dashboard v3

Interactive Streamlit dashboard for exploring what countries grow across years, using FAOSTAT crop production data with a dedicated country-comparison mode and an AI assistant.

**What's new in v3:** the AI assistant runs on a **fallback chain of free LLM
providers** — Gemini → Groq → Cerebras → OpenRouter → Mistral. They're tried in
order and when one runs out of its free quota the assistant automatically rolls
to the next, so the assistant and insights keep working. All are OpenAI-compatible,
so it's a single shared code path; you only need one key, but adding more raises
your total free daily capacity.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

## AI Assistant Setup

Do not commit your API keys to GitHub.

You need **at least one** key. Add more to increase total free daily capacity —
the app uses whichever are present, in this order:

1. **Gemini** — <https://aistudio.google.com> → "Get API key"
2. **Groq** — <https://console.groq.com/keys>
3. **Cerebras** — <https://cloud.cerebras.ai> (very generous free daily budget)
4. **OpenRouter** — <https://openrouter.ai/keys> (use a `:free` model id)
5. **Mistral** — <https://console.mistral.ai>

For local development, create `.streamlit/secrets.toml` (only the keys you have):

```toml
GEMINI_API_KEY = "your_real_gemini_api_key"
GEMINI_MODEL = "gemini-2.5-flash"

# Any of these are optional; each one extends the fallback chain
GROQ_API_KEY = "your_real_groq_api_key"
GROQ_MODEL = "llama-3.3-70b-versatile"
CEREBRAS_API_KEY = "your_real_cerebras_api_key"
CEREBRAS_MODEL = "llama-3.3-70b"
OPENROUTER_API_KEY = "your_real_openrouter_api_key"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
MISTRAL_API_KEY = "your_real_mistral_api_key"
MISTRAL_MODEL = "mistral-small-latest"
```

The assistant works with any single key. With several set, they're tried in the
order above and the app rolls to the next automatically when one hits its limit.

For Streamlit Community Cloud, add the same values in your app's **Secrets** settings.

## Deploy To Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. Go to <https://share.streamlit.io>.
3. Create a new app from your GitHub repository.
4. Set the main file path to `Project1_Codex_v3/main.py`.
5. Add at least `GEMINI_API_KEY` in the app's secrets (and any of the other provider keys above to extend the fallback chain).
6. Deploy.

## Project Versions

*"What countries grow across years"* — built iteratively across Claude and Codex.
**Version 5 is the final, recommended build.**

| # | Built with | AI Assistant | Live app | Code |
|---|------------|--------------|----------|------|
| 1 | Claude | None | [link](https://agenticaipractise-tbqheenguqz7cwbxdps6vf.streamlit.app/) | [project1](https://github.com/ravikiran1993/agentic_ai_practise/tree/main/project1) |
| 2 | Claude | None | [link](https://world-food-classic.streamlit.app/) | [project1](https://github.com/ravikiran1993/agentic_ai_practise/tree/main/project1) |
| 3 | Claude | Groq | [link](https://agenticaipractise-2u2opr3xksugktsfasm3eu.streamlit.app/) | [project1](https://github.com/ravikiran1993/agentic_ai_practise/tree/main/project1) |
| 4 | Codex | Groq | [link](https://agenticaipractise-nw5pxnbfdvaxtqnke83pwr.streamlit.app/) | [Project1_Codex_v2](https://github.com/ravikiran1993/agentic_ai_practise/tree/main/Project1_Codex_v2) |
| **5 — final** | Codex & Claude | Gemini, falling back to Groq if Gemini's limit is reached | [link](https://agenticaipractise-byaekxdyf2wwmzabspvnar.streamlit.app/) | [Project1_Codex_v3](https://github.com/ravikiran1993/agentic_ai_practise/tree/main/Project1_Codex_v3) |

> Versions 4 and 5 were built using the Superpowers skill.
