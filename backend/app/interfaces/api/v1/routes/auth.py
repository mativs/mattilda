from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.application.services.security_service import authenticate_user, create_access_token
from app.infrastructure.db.session import get_db
from app.interfaces.api.v1.schemas.auth import TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue access token",
    description="Authenticate with email/password form data and return a bearer token for protected endpoints.",
    responses={401: {"description": "Invalid credentials"}},
)
def issue_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db=db, email=form_data.username, password=form_data.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return TokenResponse(access_token=create_access_token(user.id))
