import os
from typing import Optional
from datetime import datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Corrected FastAPI-Users imports for the latest versions
from fastapi_users import models, schemas
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users.fastapi_users import FastAPIUsers

# Google API Client
from googleapiclient.discovery import build

# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- USER AUTHENTICATION MODELS ---
# The Pydantic schemas for reading, creating, and updating users
class UserRead(schemas.BaseUser[int]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass

# The SQLAlchemy model for the 'user' table in the database
class UserTable(Base, SQLAlchemyBaseUserTable):
     id = Column(Integer, primary_key=True)


# Pydantic model for database representation (used internally)
class UserDB(UserRead, models.BaseUserDB):
    pass


# --- YOUTUBE STATS DATABASE MODEL ---
class YouTubeStats(Base):
    __tablename__ = "youtube_stats"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    subscribers = Column(BigInteger)
    views = Column(BigInteger)
    videos = Column(Integer)


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

# Dependency to get the user database
async def get_user_db():
    yield SQLAlchemyUserDatabase(UserDB, engine, UserTable)

# FastAPI-Users instance with corrected schemas
fastapi_users = FastAPIUsers(
    get_user_db,
    [auth_backend],
    UserTable,
    UserRead,
    UserCreate,
    UserUpdate,
)

# --- FastAPI APP INITIALIZATION ---
app = FastAPI()

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

# Create all database tables on startup
@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)


# --- API ROUTERS ---
# Include auth routers for login, register, etc.
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"]
)

# Root endpoint
@app.get("/")
def read_root():
  return {"message": "Welcome to the TubeMetrics API"}

# Example protected endpoint
@app.get("/users/me", response_model=UserRead)
async def authenticated_route(user: UserTable = Depends(fastapi_users.get_current_active_user)):
    return user

# Note: The YouTube stats logic will be added back into new, protected endpoints later.