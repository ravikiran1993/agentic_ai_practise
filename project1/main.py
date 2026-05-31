"""
agentiki-project — Maven cohort Project 1
World food-production dashboard.

`python main.py` launches the Streamlit app. If the processed dataset is
missing, it builds it first (downloads FAOSTAT, ~34 MB).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed" / "production.parquet"


def main() -> None:
    if not DATA.exists():
        print("Processed data not found — running prepare_data.py first...\n")
        subprocess.check_call([sys.executable, str(ROOT / "prepare_data.py")])
    print("\nLaunching dashboard (Ctrl+C to stop)...")
    subprocess.check_call(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py")]
    )


if __name__ == "__main__":
    main()
