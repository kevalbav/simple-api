from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
import os
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

app = FastAPI()

# --- CORS MIDDLEWARE SETUP ---
origins = [
    "http://localhost:5173",
    # Add your deployed frontend URL once you have it
    "https://youtube-dashboard-45e6.onrender.com", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- DATA MODEL DEFINITION ---
class YouTubeStats(Base):
    __tablename__ = "youtube_stats"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    subscribers = Column(BigInteger)
    views = Column(BigInteger)
    videos = Column(Integer)

Base.metadata.create_all(bind=engine)

# --- YOUTUBE API SETUP ---
API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = "YOUR_OWN_YOUTUBE_CHANNEL_ID_HERE"

def get_youtube_stats():
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    request = youtube.channels().list(part='statistics', id=YOUTUBE_CHANNEL_ID)
    response = request.execute()
    
    if not response['items']:
        return {"error": "Channel not found"}
        
    stats = response['items'][0]['statistics']
    return {
        "subscribers": int(stats.get('subscriberCount', 0)),
        "views": int(stats.get('viewCount', 0)),
        "videos": int(stats.get('videoCount', 0))
    }

def save_stats_to_db(stats: dict):
    db = SessionLocal()
    try:
        new_stats = YouTubeStats(
            subscribers=stats['subscribers'], 
            views=stats['views'], 
            videos=stats['videos']
        )
        db.add(new_stats)
        db.commit()
        db.refresh(new_stats)
    finally:
        db.close()

# --- API ENDPOINTS ---
@app.get("/")
def read_root():
  return {"message": "Welcome to the YouTube Metrics API. Go to /stats to see data."}

@app.get("/stats")
def get_stats_and_save():
    stats = get_youtube_stats()
    if "error" not in stats:
        save_stats_to_db(stats)
    return stats

def get_latest_stats_from_db():
    db = SessionLocal()
    try:
        latest = db.query(YouTubeStats).order_by(YouTubeStats.timestamp.desc()).first()
        return latest
    finally:
        db.close()

@app.get("/historical_stats")
def show_historical_stats():
    latest_stat = get_latest_stats_from_db()
    if latest_stat is None:
        return {"message": "No historical data found. Visit /stats to save the first entry."}
    
    return {
        "last_recorded_on": latest_stat.timestamp,
        "subscribers": latest_stat.subscribers,
        "views": latest_stat.views,
        "videos": latest_stat.videos
    }