from fastapi import APIRouter

from app.interfaces.api.v1.routes.ping import router as ping_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ping_router)
