"""
Local dev entry point.

1. chdir into backend/ so pydantic-settings' relative `env_file=".env"`
   resolves regardless of the launch-time working directory.
2. Load .env into os.environ — the app reads several secrets via raw
   os.getenv() (see app/core/secrets.py), and pydantic-settings' env_file
   only populates its own Settings model, NOT the process environment.
   Without this, keys placed in .env never reach the analysis/secrets code.
"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
