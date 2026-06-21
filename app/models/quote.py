from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)

    # The quote text itself — Text type since some quotes are long
    text = Column(Text, nullable=False)

    # Author can be null for genuinely unattributed quotes
    author = Column(String, nullable=True)