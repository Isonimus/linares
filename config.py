import os

def load_env(file_path=".env"):
    """Simple manual .env loader to avoid dependencies."""
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

# Load variables at module import
load_env()

# Configuration variables
HF_TOKEN = os.environ.get("HF_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

# Catalog size controls
MIN_VOTES = int(os.environ.get("MIN_VOTES", 10000))
SETUP_FETCH_LIMIT = int(os.environ.get("SETUP_FETCH_LIMIT", 1000))

if HF_TOKEN:
    # Set it for huggingface_hub specifically if found
    os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

# Unified Rating Scale (uniform spacing for better regression target)
# Scale: 10, 8.57, 7.14, 5.71, 4.29, 2.86, 1.43, 0 (uniform ~1.43 spacing)
RATING_SCALE = {
    "1": {"label": "All-time favourite", "score": 10.0, "color": "#FFD700"},
    "2": {"label": "Love it", "score": 8.57, "color": "#FF4500"},
    "3": {"label": "Really like it", "score": 7.14, "color": "#FF8C00"},
    "4": {"label": "Like it", "score": 5.71, "color": "#FFA500"},
    "5": {"label": "Indifferent", "score": 4.29, "color": "#A9A9A9"},
    "6": {"label": "Don't like it", "score": 2.86, "color": "#696969"},
    "7": {"label": "Really don't like it", "score": 1.43, "color": "#2F4F4F"},
    "8": {"label": "Hate it", "score": 0.0, "color": "#000000"},
}

