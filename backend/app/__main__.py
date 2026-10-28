"""Run the backend: ``python -m app`` (binds to 127.0.0.1 by default)."""

import logging

import uvicorn

from .config import get_settings
from .main import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if settings.host not in ("127.0.0.1", "localhost", "::1"):
        logging.getLogger("cctv").warning(
            "Binding to %s exposes biometric search to your network", settings.host
        )
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
