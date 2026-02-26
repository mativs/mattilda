from fastapi import APIRouter

from app.interfaces.api.v1.routes.auth import router as auth_router
from app.interfaces.api.v1.routes.fees import router as fees_router
from app.interfaces.api.v1.routes.ping import router as ping_router
from app.interfaces.api.v1.routes.schools import router as schools_router
from app.interfaces.api.v1.routes.students import router as students_router
from app.interfaces.api.v1.routes.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(fees_router)
api_router.include_router(ping_router)
api_router.include_router(schools_router)
api_router.include_router(students_router)
api_router.include_router(users_router)
