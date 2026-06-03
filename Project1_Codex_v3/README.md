# FAOSTAT Crop Dashboard v3

Interactive Streamlit dashboard for exploring what countries grow across years, using FAOSTAT crop production data with a dedicated country-comparison mode and an AI assistant.

**What's new in v3:** the AI assistant now uses **Google Gemini** as the primary
provider (generous free daily request budget), with **Groq** kept as an automatic
fallback. If Gemini is unavailable or rate-limited, the assistant transparently
retries on Groq. Both use an OpenAI-compatible API, so the integration is a single
shared code path.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

## AI Assistant Setup

Do not commit your API keys to GitHub.

1. Get a free Gemini key at <https://aistudio.google.com> → **Get API key**.
2. (Optional) Get a Groq key at <https://console.groq.com> to enable the fallback.

For local development, create `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_real_gemini_api_key"
GEMINI_MODEL = "gemini-2.5-flash"

# Optional fallback — leave out to run Gemini-only
GROQ_API_KEY = "your_real_groq_api_key"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

The assistant works with either key alone. With both set, Gemini is tried first
and Groq is used automatically only if Gemini errors.

For Streamlit Community Cloud, add the same values in your app's **Secrets** settings.

## Deploy To Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. Go to <https://share.streamlit.io>.
3. Create a new app from your GitHub repository.
4. Set the main file path to `Project1_Codex_v3/main.py`.
5. Add `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`) in the app's secrets.
6. Deploy.
