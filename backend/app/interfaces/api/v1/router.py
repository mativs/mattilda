from fastapi import APIRouter

from app.interfaces.api.v1.routes.auth import router as auth_router
from app.interfaces.api.v1.routes.charges import router as charges_router
from app.interfaces.api.v1.routes.fees import router as fees_router
from app.interfaces.api.v1.routes.invoices import router as invoices_router
from app.interfaces.api.v1.routes.payments import router as payments_router
from app.interfaces.api.v1.routes.ping import router as ping_router
from app.interfaces.api.v1.routes.schools import router as schools_router
from app.interfaces.api.v1.routes.students import router as students_router
from app.interfaces.api.v1.routes.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(charges_router)
api_router.include_router(fees_router)
api_router.include_router(invoices_router)
api_router.include_router(payments_router)
api_router.include_router(ping_router)
api_router.include_router(schools_router)
api_router.include_router(students_router)
api_router.include_router(users_router)
