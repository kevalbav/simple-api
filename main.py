import os
import uuid
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from fastapi import Depends
from fastapi_users.manager import BaseUserManager, UUIDIDMixin
from sqlalchemy import String, Text, Boolean, select
from pydantic import BaseModel
from fastapi import HTTPException, status

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, BigInteger, DateTime, ForeignKey

# FastAPI-Users Imports
from fastapi_users import schemas
from fastapi_users.db import SQLAlchemyUserDatabase, SQLAlchemyBaseUserTableUUID
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users.fastapi_users import FastAPIUsers
from contextlib import asynccontextmanager
from sqlalchemy.dialects.postgresql import UUID


# --- DATABASE SETUP (Async Version) ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()




# --- DATABASE MODELS ---
class User(SQLAlchemyBaseUserTableUUID, Base):
    pass

class YouTubeStats(Base):
    __tablename__ = "youtube_stats"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    subscribers = Column(BigInteger)
    views = Column(BigInteger)
    videos = Column(Integer)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"))


# --- PYDANTIC SCHEMAS ---
class UserRead(schemas.BaseUser[uuid.UUID]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass


# --- DATABASE DEPENDENCY ---
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

    # simple-api/main.py (below get_user_db)
class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = os.getenv("SECRET_KEY", "dev-secret")
    verification_token_secret = os.getenv("SECRET_KEY", "dev-secret")

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


# --- AUTHENTICATION SETUP ---
SECRET = os.getenv("SECRET_KEY", "a_default_secret_key_for_local_dev")
cookie_transport = CookieTransport(cookie_name="tubemetrics", 
    cookie_max_age=3600,cookie_secure=True,
    cookie_samesite="none",
    cookie_httponly=True,)


class OnboardingProfile(Base):
    __tablename__ = "onboarding_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), unique=True, nullable=False)

    role = Column(String(100), nullable=False)                  # e.g., "Solo creator"
    primary_goal = Column(String(200), nullable=False)          # e.g., "Increase retention"
    niche = Column(String(200), nullable=True)                  # e.g., "Tech explainers"
    posting_cadence = Column(String(50), nullable=True)         # e.g., "2/wk"
    audience_desc = Column(Text, nullable=True)
    is_complete = Column(Boolean, default=True)

    class OnboardingIn(BaseModel):
        role: str
        primary_goal: str
        niche: str | None = None
        posting_cadence: str | None = None
        audience_desc: str | None = None
        is_complete: bool = True

class OnboardingOut(OnboardingIn):
    id: int


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)


# --- APP LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

# --- CORS MIDDLEWARE (CORRECTLY INCLUDED) ---
origins = [
    "http://localhost:5173",
    "https://youtube-dashboard-45e6.onrender.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,   # <- important
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- API ROUTERS ---
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
# ---- Onboarding Schemas ----
class OnboardingIn(BaseModel):
    role: str
    primary_goal: str
    niche: str | None = None
    posting_cadence: str | None = None
    audience_desc: str | None = None
    is_complete: bool = True

class OnboardingOut(OnboardingIn):
    id: int

# ---- Onboarding Routes ----
@app.post("/onboarding", response_model=OnboardingOut)
async def upsert_onboarding(
    payload: OnboardingIn,
    user: User = Depends(fastapi_users.current_user()),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(OnboardingProfile).where(OnboardingProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = OnboardingProfile(
            user_id=user.id,
            role=payload.role,
            primary_goal=payload.primary_goal,
            niche=payload.niche,
            posting_cadence=payload.posting_cadence,
            audience_desc=payload.audience_desc,
            is_complete=payload.is_complete,
        )
        session.add(profile)
    else:
        profile.role = payload.role
        profile.primary_goal = payload.primary_goal
        profile.niche = payload.niche
        profile.posting_cadence = payload.posting_cadence
        profile.audience_desc = payload.audience_desc
        profile.is_complete = payload.is_complete

    await session.commit()
    await session.refresh(profile)
    return profile

@app.get("/onboarding/me", response_model=OnboardingOut)
async def get_my_onboarding(
    user: User = Depends(fastapi_users.current_user()),
    session: AsyncSession = Depends(get_async_session),
):
    result = await session.execute(
        select(OnboardingProfile).where(OnboardingProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding not found")
    return profile

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the TubeMetrics API"}

# Example protected endpoint
@app.get("/users/me", response_model=UserRead)
async def authenticated_route(user: User = Depends(fastapi_users.current_user())):
    return user