
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
import os
import uuid

from backend.database import engine, Base, SessionLocal
from backend import models, schemas

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Handwritten Notes API")

password_hash = PasswordHash.recommended()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "Handwritten Notes Website is Running"}


@app.post("/register")
def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(models.User)
        .filter(models.User.email == user.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    if len(user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters"
        )

    hashed_password = password_hash.hash(user.password)

    new_user = models.User(
        name=user.name,
        email=user.email,
        password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user_id": new_user.id
    }


@app.post("/login")
def login_user(
    user: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(models.User)
        .filter(models.User.email == user.email)
        .first()
    )

    if existing_user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not password_hash.verify(
        user.password,
        existing_user.password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return {
        "message": "Login successful",
        "user_id": existing_user.id,
        "name": existing_user.name
    }


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
    user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid user"
        )

    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg"}

    original_name = os.path.basename(file.filename or "")
    extension = os.path.splitext(original_name)[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, PNG, JPG and JPEG files are allowed"
        )

    os.makedirs("uploads", exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{extension}"
    file_path = os.path.join("uploads", stored_name)

    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)

        new_note = models.Note(
            title=title,
            subject=subject,
            topic=topic,
            description=description,
            file_path=file_path,
            user_id=user_id
        )

        db.add(new_note)
        db.commit()
        db.refresh(new_note)

    except Exception:
        db.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=500,
            detail="Unable to upload note"
        )

    return {
        "message": "Note uploaded successfully",
        "note_id": new_note.id,
        "title": new_note.title,
        "subject": new_note.subject,
        "topic": new_note.topic,
        "description": new_note.description,
        "file": original_name,
        "user_id": user_id
    }


@app.get("/notes")
def get_notes(db: Session = Depends(get_db)):
    return db.query(models.Note).all()


@app.get("/my-notes/{user_id}")
def get_my_notes(
    user_id: int,
    db: Session = Depends(get_db)
):
    return (
        db.query(models.Note)
        .filter(models.Note.user_id == user_id)
        .all()
    )


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
    note = (
        db.query(models.Note)
        .filter(models.Note.id == note_id)
        .first()
    )

    if note is None:
        raise HTTPException(
            status_code=404,
            detail="Note not found"
        )

    if note.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot edit this note"
        )

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


@app.delete("/delete-note/{note_id}/{user_id}")
def delete_note(
    note_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    note = (
        db.query(models.Note)
        .filter(models.Note.id == note_id)
        .first()
    )

    if note is None:
        raise HTTPException(
            status_code=404,
            detail="Note not found"
        )

    if note.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You cannot delete this note"
        )

    file_path = note.file_path

    db.delete(note)
    db.commit()

    if os.path.exists(file_path):
        os.remove(file_path)

    return {"message": "Note deleted successfully"}


@app.get("/view-note/{note_id}")
def view_note(
    note_id: int,
    db: Session = Depends(get_db)
):
    note = (
        db.query(models.Note)
        .filter(models.Note.id == note_id)
        .first()
    )

    if note is None:
        raise HTTPException(
            status_code=404,
            detail="Note not found"
        )

    if not os.path.exists(note.file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    note.views = (note.views or 0) + 1
    db.commit()

    return FileResponse(note.file_path)