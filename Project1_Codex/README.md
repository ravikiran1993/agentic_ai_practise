# FAOSTAT Crop Dashboard

Interactive Streamlit dashboard for exploring what countries grow across years, using FAOSTAT crop production data with an AI assistant powered by Groq.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

## AI Assistant Setup

Do not commit your API key to GitHub.

For local development, create `.streamlit/secrets.toml`:

```toml
GROQ_API_KEY = "your_real_groq_api_key"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

For Streamlit Community Cloud, add the same values in your app's **Secrets** settings.

## Deploy To Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. Go to `https://share.streamlit.io`.
3. Create a new app from your GitHub repository.
4. Set the main file path to `main.py`.
5. Add `GROQ_API_KEY` and optionally `GROQ_MODEL` in the app's secrets.
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
