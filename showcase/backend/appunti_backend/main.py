from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from appunti_backend.api.router import api_router
from appunti_backend.core.config import settings
from appunti_backend.lifecycle import lifespan


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "environment": settings.env,
        "transport": "https" if settings.use_https else "http",
        "api": settings.api_v1_prefix,
        "docs": "/docs",
    }


def main() -> None:
    if settings.use_https:
        if not settings.ssl_certfile or not settings.ssl_certfile.exists():
            raise RuntimeError(f"Certificato HTTPS non trovato: {settings.ssl_certfile}")
        if not settings.ssl_keyfile or not settings.ssl_keyfile.exists():
            raise RuntimeError(f"Chiave HTTPS non trovata: {settings.ssl_keyfile}")

    uvicorn.run(
        "appunti_backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        ssl_keyfile=str(settings.ssl_keyfile) if settings.use_https and settings.ssl_keyfile else None,
        ssl_certfile=str(settings.ssl_certfile) if settings.use_https and settings.ssl_certfile else None,
    )


if __name__ == "__main__":
    main()
