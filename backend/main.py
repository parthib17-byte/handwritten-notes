from fastapi import (
    FastAPI, Depends, UploadFile, File, Form
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import engine, Base, SessionLocal
from backend import models, schemas

from pathlib import Path
import hashlib
import hmac
import os
import secrets
import uuid


# -------------------------------
# PATHS AND DATABASE
# -------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Handwritten Notes API")


# -------------------------------
# CORS
# -------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# PASSWORD HELPERS
# -------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        600_000
    ).hex()

    return f"pbkdf2_sha256$600000${salt}${hashed}"


def verify_password(password: str, stored_password: str) -> bool:
    try:
        if not stored_password.startswith("pbkdf2_sha256$"):
            # Support accounts created by the old version.
            return hmac.compare_digest(password, stored_password)

        algorithm, iterations, salt, saved_hash = (
            stored_password.split("$", 3)
        )

        calculated_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations)
        ).hex()

        return hmac.compare_digest(calculated_hash, saved_hash)

    except (ValueError, TypeError):
        return False


# -------------------------------
# DATABASE CONNECTION
# -------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------
# FILE PATH HELPER
# -------------------------------

def get_file_path(file_path: str) -> Path:
    path = Path(file_path)

    if not path.is_absolute():
        path = BASE_DIR / path

    return path


# -------------------------------
# HOME
# -------------------------------

@app.get("/")
def home():
    return {
        "message": "Handwritten Notes Website is Running"
    }


# -------------------------------
# REGISTER
# -------------------------------

@app.post("/register")
def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        return {"message": "Email already registered"}

    new_user = models.User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user_id": new_user.id
    }


# -------------------------------
# LOGIN
# -------------------------------

@app.post("/login")
def login_user(
    user: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user is None:
        return {"message": "User not found"}

    if not verify_password(
        user.password, existing_user.password
    ):
        return {"message": "Incorrect password"}

    # Upgrade old plaintext passwords after successful login.
    if not existing_user.password.startswith("pbkdf2_sha256$"):
        existing_user.password = hash_password(user.password)
        db.commit()

    return {
        "message": "Login successful",
        "user_id": existing_user.id,
        "name": existing_user.name
    }


# -------------------------------
# UPLOAD NOTE
# -------------------------------

@app.post("/upload-note")
def upload_note(
    title: str = Form(...),
    subject: str = Form(...),
    topic: str = Form(""),
    description: str = Form(""),
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.id == user_id
    ).first()

    if user is None:
        return {"message": "User not found"}

    if not file.filename:
        return {"message": "No file selected"}

    extension = Path(file.filename).suffix.lower()
    saved_name = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / saved_name

    try:
        with destination.open("wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                buffer.write(chunk)

        new_note = models.Note(
            title=title,
            subject=subject,
            topic=topic,
            description=description,
            file_path=str(destination),
            user_id=user_id
        )

        db.add(new_note)
        db.commit()
        db.refresh(new_note)

        return {
            "message": "Note uploaded successfully",
            "note_id": new_note.id,
            "title": new_note.title,
            "subject": new_note.subject,
            "topic": new_note.topic,
            "description": new_note.description,
            "file": file.filename,
            "user_id": user_id
        }

    except Exception:
        db.rollback()
        if destination.exists():
            destination.unlink()
        raise

    finally:
        file.file.close()


# -------------------------------
# GET ALL NOTES
# -------------------------------

@app.get("/notes")
def get_notes(db: Session = Depends(get_db)):
    return db.query(models.Note).all()


# -------------------------------
# GET MY NOTES
# -------------------------------

@app.get("/my-notes/{user_id}")
def get_my_notes(
    user_id: int,
    db: Session = Depends(get_db)
):
    return db.query(models.Note).filter(
        models.Note.user_id == user_id
    ).all()


# -------------------------------
# EDIT NOTE
# -------------------------------

@app.put("/edit-note/{note_id}")
def edit_note(
    note_id: int,
    title: str = Form(...),
    subject: str = Form(...),
    topic: str = Form(""),
    description: str = Form(""),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    note = db.query(models.Note).filter(
        models.Note.id == note_id
    ).first()

    if note is None:
        return {"message": "Note not found"}

    if note.user_id != user_id:
        return {"message": "You cannot edit this note"}

    note.title = title
    note.subject = subject
    note.topic = topic
    note.description = description

    db.commit()
    db.refresh(note)

    return {
        "message": "Note updated successfully",
        "note_id": note.id
    }


# -------------------------------
# DELETE NOTE
# -------------------------------

@app.delete("/delete-note/{note_id}/{user_id}")
def delete_note(
    note_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    note = db.query(models.Note).filter(
        models.Note.id == note_id
    ).first()

    if note is None:
        return {"message": "Note not found"}

    if note.user_id != user_id:
        return {"message": "You cannot delete this note"}

    path = get_file_path(note.file_path)

    try:
        db.delete(note)
        db.commit()

        if path.is_file():
            path.unlink()

        return {"message": "Note deleted successfully"}

    except Exception:
        db.rollback()
        raise


# -------------------------------
# VIEW NOTE
# -------------------------------

@app.get("/view-note/{note_id}")
def view_note(
    note_id: int,
    db: Session = Depends(get_db)
):
    note = db.query(models.Note).filter(
        models.Note.id == note_id
    ).first()

    if note is None:
        return {"message": "Note not found"}

    path = get_file_path(note.file_path)

    if not path.is_file():
        return {"message": "File not found"}

    note.views = (note.views or 0) + 1
    db.commit()

    return FileResponse(path=str(path))