# FAOSTAT Crop Dashboard v2

Interactive Streamlit dashboard for exploring what countries grow across years, using FAOSTAT crop production data with a dedicated country-comparison mode and an AI assistant powered by Groq.

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

For this v2 folder, set the Streamlit main file path to `Project1_Codex_v2/main.py`.
