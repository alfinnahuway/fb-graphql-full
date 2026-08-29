"""Configuration for Facebook GraphQL Full Scraper."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
FB_COOKIES_PATH = os.getenv("FB_COOKIES_PATH", str(BASE_DIR / "fb_cookies.txt"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output")))
DEFAULT_MAX_POSTS = int(os.getenv("DEFAULT_MAX_POSTS", "5"))
DEFAULT_MAX_COMMENTS = int(os.getenv("DEFAULT_MAX_COMMENTS", "100"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
