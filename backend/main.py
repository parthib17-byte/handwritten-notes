from fastapi import FastAPI, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from backend.database import engine, Base, SessionLocal
from backend import models, schemas


# =====================================
# CREATE DATABASE TABLES
# =====================================

Base.metadata.create_all(bind=engine)


# =====================================
# CREATE FASTAPI APP
# =====================================

app = FastAPI()


# =====================================
# CORS
# =====================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================
# DATABASE CONNECTION
# =====================================

def get_db():

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =====================================
# HOME
# =====================================

@app.get("/")
def home():

    return {
        "message": "Handwritten Notes Website is Running"
    }


# =====================================
# REGISTER
# =====================================

@app.post("/register")
def register_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = db.query(
        models.User
    ).filter(
        models.User.email == user.email
    ).first()

    if existing_user:

        return {
            "message": "Email already registered"
        }

    new_user = models.User(
        name=user.name,
        email=user.email,
        password=user.password
    )

    db.add(new_user)

    db.commit()

    db.refresh(new_user)

    return {

        "message": "User registered successfully",

        "user_id": new_user.id

    }


# =====================================
# LOGIN
# =====================================

@app.post("/login")
def login_user(
    user: schemas.UserLogin,
    db: Session = Depends(get_db)
):

    existing_user = db.query(
        models.User
    ).filter(
        models.User.email == user.email
    ).first()

    if existing_user is None:

        return {
            "message": "User not found"
        }

    if existing_user.password != user.password:

        return {
            "message": "Incorrect password"
        }

    return {

        "message": "Login successful",

        "user_id": existing_user.id,

        "name": existing_user.name

    }


# =====================================
# UPLOAD NOTE
# =====================================

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

    os.makedirs(
        "uploads",
        exist_ok=True
    )

    file_path = (
        f"uploads/{file.filename}"
    )

    with open(
        file_path,
        "wb"
    ) as buffer:

        buffer.write(
            file.file.read()
        )

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


# =====================================
# GET ALL NOTES
# =====================================

@app.get("/notes")
def get_notes(
    db: Session = Depends(get_db)
):

    notes = db.query(
        models.Note
    ).all()

    return notes


# =====================================
# GET MY NOTES
# =====================================

@app.get("/my-notes/{user_id}")
def get_my_notes(

    user_id: int,

    db: Session = Depends(get_db)

):

    notes = db.query(
        models.Note
    ).filter(
        models.Note.user_id == user_id
    ).all()

    return notes


# =====================================
# EDIT NOTE
# =====================================

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

    note = db.query(
        models.Note
    ).filter(
        models.Note.id == note_id
    ).first()

    if note is None:

        return {
            "message": "Note not found"
        }

    if note.user_id != user_id:

        return {
            "message": "You cannot edit this note"
        }

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


# =====================================
# DELETE NOTE
# =====================================

@app.delete("/delete-note/{note_id}/{user_id}")
def delete_note(

    note_id: int,

    user_id: int,

    db: Session = Depends(get_db)

):

    note = db.query(
        models.Note
    ).filter(
        models.Note.id == note_id
    ).first()

    if note is None:

        return {
            "message": "Note not found"
        }

    if note.user_id != user_id:

        return {
            "message": "You cannot delete this note"
        }

    if os.path.exists(
        note.file_path
    ):

        os.remove(
            note.file_path
        )

    db.delete(note)

    db.commit()

    return {

        "message": "Note deleted successfully"

    }


# =====================================
# VIEW NOTE
# =====================================

@app.get("/view-note/{note_id}")
def view_note(

    note_id: int,

    db: Session = Depends(get_db)

):

    note = db.query(
        models.Note
    ).filter(
        models.Note.id == note_id
    ).first()

    if note is None:

        return {
            "message": "Note not found"
        }

    if not os.path.exists(
        note.file_path
    ):

        return {
            "message": "File not found"
        }

    note.views = note.views + 1

    db.commit()

    return FileResponse(
        note.file_path
    )