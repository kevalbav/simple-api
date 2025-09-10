import os
import uuid
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from fastapi import Depends
from fastapi_users.manager import BaseUserManager, UUIDIDMixin

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
    cookie_max_age=3600,ookie_secure=True,
    cookie_samesite="none",
    cookie_httponly=True,)

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

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the TubeMetrics API"}

# Example protected endpoint
@app.get("/users/me", response_model=UserRead)
async def authenticated_route(user: User = Depends(fastapi_users.current_user())):
    return user