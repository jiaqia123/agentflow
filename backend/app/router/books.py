from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.mysql import get_db
from app.models.books import Book
from app.schemas.books import BookCreate, BookUpdate

router = APIRouter(prefix="/books", tags=["books"])

@router.post("", status_code=201)
def create_book(book_in: BookCreate, db: Session = Depends(get_db)):
    db_book = Book(**book_in.model_dump())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book

@router.get("")
def read_books(page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    skip = (page - 1) * limit
    books = db.query(Book).offset(skip).limit(limit).all()
    return books

@router.get("/{book_id}")
def read_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    return book

@router.post("/{book_id}/update")
def update_book(book_id: int, book_update: BookUpdate, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if book_update.title is not None:
        book.title = book_update.title
    if book_update.author is not None:
        book.author = book_update.author

    db.commit()
    db.refresh(book)
    return book

@router.post("/{book_id}/delete")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    db.delete(book)
    db.commit()
    return {"message": "删除成功"}
