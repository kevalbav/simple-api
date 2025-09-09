from fastapi import FastAPI
from googleapiclient.discovery import build
import os
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# --- DATABASE SETUP ---
# Render provides the DATABASE_URL environment variable.
DATABASE_URL = os.getenv("DATABASE_URL")

# Create the SQLAlchemy engine. The 'connect_args' is for Render's SSL.
engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})

# Create a session to interact with the database.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our data models.
Base = declarative_base()

# --- DATA MODEL DEFINITION ---
# This class defines the 'youtube_stats' table in our database.
class YouTubeStats(Base):
    __tablename__ = "youtube_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    subscribers = Column(Integer)
    views = Column(Integer)
    videos = Column(Integer)

# Create the table in the database if it doesn't exist.
Base.metadata.create_all(bind=engine)


# --- YOUTUBE API SETUP ---
app = FastAPI()
API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = "UC-lHJZR3Gqxm24_Vd_AJ5Yw" # Google Developers channel

def get_youtube_stats():
    # This function remains the same.
    youtube = build('youtube', 'v3', developerKey=API_KEY)
    request = youtube.channels().list(
        part='statistics',
        id=YOUTUBE_CHANNEL_ID
    )
    response = request.execute()
    stats = response['items'][0]['statistics']
    return {
        "subscribers": int(stats['subscriberCount']),
        "views": int(stats['viewCount']),
        "videos": int(stats['videoCount'])
    }

# --- NEW DATABASE FUNCTION ---
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
    # 1. Fetch fresh stats from YouTube.
    stats = get_youtube_stats()
    
    # 2. Save the fresh stats to our database.
    save_stats_to_db(stats)
    
    # 3. Return the stats.
    return stats