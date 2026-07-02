"""
Local dev entry point — chdirs into backend/ before starting uvicorn so
pydantic-settings' relative `env_file=".env"` resolves correctly
regardless of the process's launch-time working directory.
"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
