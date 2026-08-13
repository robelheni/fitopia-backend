from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey
from datetime import datetime
from app.database import Base

class TrainerApplication(Base):
    __tablename__ = "trainer_applications"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    bio = Column(Text, nullable=True)
    speciality = Column(String, nullable=True)
    location = Column(String, nullable=True)
    languages = Column(String, nullable=True)
    years_experience = Column(Integer, nullable=True)
    certifications = Column(Text, nullable=True)
    hourly_rate = Column(Float, nullable=True)
    instagram = Column(String, nullable=True)
    whatsapp  = Column(String, nullable=True)

    # pending, approved, rejected
    status = Column(String, default="pending")
    admin_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
