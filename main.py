import os
from typing import Optional
from datetime import datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from fastapi_users import schemas, models
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users.fastapi_users import FastAPIUsers

# --- DATABASE SETUP (Slightly modified for async) ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- USER MODEL & DATABASE TABLE DEFINITION ---
class User(models.BaseUser):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass

class UserDB(User, models.BaseUserDB):
    pass
    
class UserTable(Base, SQLAlchemyBaseUserTable):
    pass

# --- AUTHENTICATION SETUP ---
SECRET = os.getenv("SECRET_KEY", "a_default_secret_key_for_local_dev") # IMPORTANT: Set this in Render

cookie_transport = CookieTransport(cookie_name="tubemetrics", cookie_max_age=3600)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

# Dependency to get the user DB
async def get_user_db():
    yield SQLAlchemyUserDatabase(UserDB, engine, UserTable)

fastapi_users = FastAPIUsers(
    get_user_db,
    [auth_backend],
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)

# --- FastAPI App Initialization ---
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

# --- INCLUDE AUTH ROUTERS ---
# This automatically creates /login, /register, /logout etc.
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(),
    prefix="/auth",
    tags=["auth"],
)
# We can add more routers for password reset, etc. later

# Create all database tables on startup
@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)

# --- Example Protected Endpoint ---
@app.get("/users/me")
async def authenticated_route(user: User = Depends(fastapi_users.get_current_active_user)):
    return {"message": f"Hello {user.email}!"}

@app.get("/")
def read_root():
  return {"message": "Welcome to the TubeMetrics API"}

# Note: The YouTube stats logic will be added back into new, protected endpoints later.