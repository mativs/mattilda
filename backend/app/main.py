from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.application.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.config import settings
from app.infrastructure.logging import configure_logging, get_logger
from app.interfaces.api.v1.router import api_router

logger = get_logger(__name__)

OPENAPI_DESCRIPTION = """
School finance API for managing schools, students, charges, invoices, payments, and reconciliation.

How to call this API:
- Authenticate at `POST /api/v1/auth/token`.
- Use `Authorization: Bearer <access_token>` in protected endpoints.
- For school-scoped endpoints, send `X-School-Id` with a school where the user has membership.
"""

OPENAPI_TAGS = [
    {"name": "health", "description": "Service health and connectivity checks."},
    {"name": "auth", "description": "Authentication and token issuance."},
    {"name": "users", "description": "User profile, memberships, and user management in school context."},
    {"name": "schools", "description": "School CRUD, financial summary, school-wide tasks, and reconciliation."},
    {"name": "students", "description": "Student CRUD, visibility-aware access, and student financial views."},
    {"name": "fees", "description": "Fee definition configuration for a school (admin-managed)."},
    {"name": "charges", "description": "Atomic debt records associated with students and invoices."},
    {"name": "invoices", "description": "Invoice reads and controlled invoice generation flows."},
    {"name": "payments", "description": "Payment creation and visibility-aware payment reads."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger.info("app_startup", app_name=settings.app_name, version=settings.app_version)
    yield
    logger.info("app_shutdown", app_name=settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=OPENAPI_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:13000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Mattilda take-home environment is running"}


@app.exception_handler(NotFoundError)
async def handle_not_found(_: Request, exc: NotFoundError):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def handle_conflict(_: Request, exc: ConflictError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(ForbiddenError)
async def handle_forbidden(_: Request, exc: ForbiddenError):
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def handle_validation(_: Request, exc: ValidationError):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


app.include_router(api_router)
