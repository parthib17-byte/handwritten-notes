from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

    notes = relationship("Note", back_populates="owner")


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    subject = Column(String(100), nullable=False)
    topic = Column(String(200))
    description = Column(Text)
    file_path = Column(String(500), nullable=False)
    views = Column(Integer, default=0)

    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="notes")