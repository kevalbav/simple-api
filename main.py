import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Corrected FastAPI-Users imports for the latest versions
from fastapi_users import schemas
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.fastapi_users import FastAPIUsers
from fastapi_users.models import BaseUserDB

# Google API Client (optional for now)
# from googleapiclient.discovery import build


# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)  # Removed sslmode for broader compatibility, Render injects it.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- DATABASE MODELS ---

# The SQLAlchemy model for the 'user' table in the database
class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


class YouTubeStats(Base):
    __tablename__ = "youtube_stats"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    subscribers = Column(BigInteger)
    views = Column(BigInteger)
    videos = Column(Integer)
    # Link to a user
    user_id = Column(uuid.UUID, ForeignKey("user.id"))


# --- PYDANTIC SCHEMAS ---

# Pydantic schemas for reading and creating users
class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


# --- AUTHENTICATION SETUP ---
SECRET = os.getenv("SECRET_KEY", "a_default_secret_key_for_local_dev")

cookie_transport = CookieTransport(cookie_name="tubemetrics", cookie_max_age=3600)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    Base.metadata.create_all(bind=engine)
    yield
    # Code to run on shutdown (if any)

# Dependency to get the user database
async def get_user_db():
    yield SQLAlchemyUserDatabase(User, engine)


fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_db,
    [auth_backend],
    User,
    UserCreate,
    UserRead,
    UserUpdate,
)


# --- FastAPI APP INITIALIZATION ---
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
origins = [
    "http://localhost:5173",
    "https://youtube-dashboard-45e6.onrender.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# --- API ROUTERS ---
# Include auth routers for login, register, etc.
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)


# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the TubeMetrics API"}


# Example protected endpoint
@app.get("/users/me", response_model=UserRead)
async def authenticated_route(
    user: User = Depends(fastapi_users.get_current_active_user),
):
    return user


# We will re-add the YouTube stats logic in protected endpoints next.