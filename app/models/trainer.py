from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float
from datetime import datetime
from app.database import Base

class Trainer(Base):
    __tablename__ = "trainers"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    bio = Column(Text, nullable=True)
    speciality = Column(String, nullable=True)
    location = Column(String, nullable=True)
    languages = Column(String, nullable=True)  # comma-separated e.g. "English,Amharic"

    years_experience = Column(Integer, nullable=True)
    clients_trained = Column(Integer, nullable=True)
    certifications = Column(Text, nullable=True)

    hourly_rate = Column(Float, nullable=True)

    profile_picture = Column(String, nullable=True)  # Cloudinary URL
    transformation_pictures = Column(Text, nullable=True)  # comma-separated URLs

    instagram = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)

    is_verified = Column(Boolean, default=False)  # admin approves this
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
