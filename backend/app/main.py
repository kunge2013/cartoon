# -*- coding: utf-8 -*-
"""catong_gen FastAPI 入口（Phase 0/1 骨架）。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME, APP_VERSION
from app.database import Base, engine
from app.routers import assemble, novels, prompts, roles, settings, projects, images, image_derive, image_generation, export, art_styles

app = FastAPI(title=f"{APP_NAME} API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(engine)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}


app.include_router(prompts.router, prefix="/api")
app.include_router(assemble.router, prefix="/api")
app.include_router(novels.router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(image_derive.router, prefix="/api")
app.include_router(image_generation.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(art_styles.router, prefix="/api")
