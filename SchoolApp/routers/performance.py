import os
import pandas as pd
from datetime import datetime



from starlette import status
from starlette.responses import RedirectResponse
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends, APIRouter, Form, HTTPException, Path, Request, File, UploadFile
from starlette import status
from SchoolApp import models
from ..models import Performance, Students, Subjects, Teachers
from ..database import SessionLocal, engine
from .auth import get_current_user

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    responses={404: {"description": "Not found"}}
)

models.Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="SchoolApp/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

class PerformanceRequest(BaseModel):
    student_id: int
    subject_id: int
    teacher_id: int
    exam_id: int
    exam_date: int
    exam_type: str = Field(..., description="Type of the exam, case insensitive")
    performance: int = Field(gt=0, lt=101)

    # Override the model's initialization to ensure exam_type is stored in lowercase
    def __init__(self, **data):
        super().__init__(**data)
        self.exam_type = self.exam_type.lower()

@router.get('/student/{student_id}', response_class=HTMLResponse)
async def student_dashboard(request: Request, student_id: int, db: Session = Depends(get_db)):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)


    performance_records = db.query(models.Performance)\
        .filter(models.Performance.student_id == student_id)\
        .all()
    
    return templates.TemplateResponse("home.html", {
        "request": request, 
        "performance": performance_records, 
        "user": user
    })


@router.get('/student/{student_id}/results', response_class=HTMLResponse)
async def student_dashboard(request: Request, student_id: int, db: Session = Depends(get_db)):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    # Fetch the student's performance data and join it with the Subjects table
    performance_records = db.query(models.Performance, models.Subjects)\
        .join(models.Subjects, models.Performance.subject_id == models.Subjects.id)\
        .filter(models.Performance.student_id == student_id)\
        .all()

    # Pass the performance data to the template
    return templates.TemplateResponse("results.html", {
        "request": request,
        "performances": performance_records,  # Use plural to indicate multiple records
        "user": user
    })



@router.get('/teacher/{teacher_id}', response_class=HTMLResponse)
async def teacher_dashboard(request: Request, teacher_id: int, db: Session = Depends(get_db)):
    user = await get_current_user(request)  # Ensure this function is async
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    # Query to fetch all students' performance for the subjects the teacher teaches
    performance_records = db.query(models.Performance)\
        .filter(models.Performance.teacher_id == teacher_id)\
        .all()
    
    # Fetching the teacher and their subject
    teacher = db.query(models.Teachers)\
        .filter(models.Teachers.id == teacher_id)\
        .first()

    # Access the subject from the teacher object
    subject = teacher.subjects if teacher else None

    return templates.TemplateResponse("teachers-page.html", {
        "request": request, 
        "performances": performance_records,
        "subject": subject,  # This will pass the subject to the template
        "user": user
    })


@router.post("/upload-csv", response_class=HTMLResponse)
async def upload_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    if not file.filename.endswith('.csv'):
        return templates.TemplateResponse("error.html", {"request": request, "error": "Invalid file type. Please upload a CSV file."})

    # Read the CSV file into a pandas DataFrame
    try:
        df = pd.read_csv(file.file)
    except Exception as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": f"Error reading the CSV file: {str(e)}"})

    # Validate the required columns
    required_columns = ['student_id', 'subject_id', 'teacher_id', 'exam_id', 'exam_date', 'exam_type', 'performance']
    for col in required_columns:
        if col not in df.columns:
            return templates.TemplateResponse("error.html", {"request": request, "error": f"Missing required column: {col}"})

    # Validate data types and performance scores
    errors = []
    for index, row in df.iterrows():
        if not isinstance(row['student_id'], int) or row['student_id'] <= 0:
            errors.append(f"Invalid student_id at row {index + 1}.")
        if not isinstance(row['subject_id'], int) or row['subject_id'] <= 0:
            errors.append(f"Invalid subject_id at row {index + 1}.")
        if not isinstance(row['teacher_id'], int) or row['teacher_id'] <= 0:
            errors.append(f"Invalid teacher_id at row {index + 1}.")
        if not isinstance(row['exam_id'], int) or row['exam_id'] <= 0:
            errors.append(f"Invalid exam_id at row {index + 1}.")
        if not isinstance(row['exam_date'], int) or row['exam_date'] <= 0:
            errors.append(f"Invalid exam_date at row {index + 1}.")
        if not isinstance(row['exam_type'], str) or not row['exam_type']:
            errors.append(f"Invalid exam_type at row {index + 1}.")
        if not (isinstance(row['performance'], int) and 0 <= row['performance'] <= 100):
            errors.append(f"Invalid performance score at row {index + 1}. Must be between 0 and 100.")

    if errors:
        return templates.TemplateResponse("error.html", {"request": request, "error": "<br>".join(errors)})

    # If all validations pass, save the records to the database
    for _, row in df.iterrows():
        performance_model = Performance(
            student_id=row['student_id'],
            subject_id=row['subject_id'],
            teacher_id=row['teacher_id'],
            exam_id=row['exam_id'],
            exam_date=row['exam_date'],
            exam_type=row['exam_type'],
            performance=row['performance']
        )
        db.add(performance_model)

    db.commit()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@router.get("/teacher/{teacher_id}/add-performance", response_class=HTMLResponse)
async def add_performance(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=302)

    # Fetch the list of students, subjects, etc., that the teacher can add performance for.
    students = db.query(models.Students).all()
    subjects = db.query(models.Subjects).all()

    return templates.TemplateResponse("add-performance.html", {"request": request, "user": user, "students": students, "subjects": subjects})

@router.post("/teacher/{teacher_id}/add-performance", response_class=HTMLResponse)
async def create_performance(request: Request, student_id: str = Form(...),
                             exam_type: str = Form(...), exam_date: str = Form(...),
                             performance: int = Form(...), teacher_id: int = Path(...), 
                             db: Session = Depends(get_db)):

    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    # Convert exam_type to lowercase
    exam_type = exam_type.lower()

    # Convert the exam_date to a datetime object
    try:
        exam_date = datetime.strptime(exam_date, "%d-%m-%Y").date()
    except ValueError:
        # If date format is invalid, return the form with an error message
        return templates.TemplateResponse("add-performance.html", {
            "request": request,
            "msg": "Invalid date format. Use DD-MM-YYYY.",
            "user": user
        })

    # Retrieve student and teacher based on IDs provided
    student = db.query(models.Students).filter(models.Students.username == student_id).first()
    teacher = db.query(models.Teachers).filter(models.Teachers.id == teacher_id).first()

    # Handle not found cases
    if not student:
        return templates.TemplateResponse("add-performance.html", {
            "request": request,
            "msg": "Student not found.",
            "user": user
        })
    if not teacher:
        return templates.TemplateResponse("add-performance.html", {
            "request": request,
            "msg": "Teacher not found.",
            "user": user
        })

    # Fetch the subject using teacher's subject
    subject = db.query(models.Subjects).filter(models.Subjects.subject_name == teacher.subjects).first()
    if not subject:
        return templates.TemplateResponse("add-performance.html", {
            "request": request,
            "msg": "Subject not found for the teacher.",
            "user": user
        })

    # Create a new performance record
    performance_model = models.Performance(
        student_id=student.id,
        subject_id=subject.id,
        student_username=student.username,
        subject_name=subject.subject_name,
        teacher_id=teacher.id,
        exam_type=exam_type,
        exam_date=exam_date,
        performance=performance
    )

    try:
        # Add performance to the database
        db.add(performance_model)
        db.commit()
        msg = "Student Performance successfully created"
    except Exception as e:
        # Rollback in case of error and render the template with an error message
        db.rollback()
        msg = f"Error occurred: {str(e)}"
        return templates.TemplateResponse("add-performance.html", {
            "request": request,
            "msg": msg,
            "user": user
        })

    # On success, redirect to teacher's dashboard with a success message
    return RedirectResponse(url=f'/dashboard/teacher/{teacher.id}', status_code=status.HTTP_302_FOUND)


@router.get("/teacher/{teacher_id}/edit-performance/{performance_id}", response_class=HTMLResponse)
async def edit_performance(request: Request, performance_id: int, db: Session = Depends(get_db)):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    # Retrieve the existing performance record
    performance = db.query(models.Performance).filter(models.Performance.id == performance_id).first()

    if not performance:
        raise HTTPException(status_code=404, detail="Performance record not found")

    return templates.TemplateResponse("edit-performance.html", {
        "request": request, 
        "performance": performance, 
        "user": user
    })



@router.post("/teacher/{teacher_id}/edit-performance/{performance_id}", response_class=HTMLResponse)
async def edit_performance_commit(request: Request, performance_id: int, student_id: str = Form(...), 
                                  subject_name: str = Form(...), teacher_id: int = Path(...), 
                                  exam_date: str = Form(...), exam_type: str = Form(...), 
                                  performance: int = Form(...), db: Session = Depends(get_db)):

    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    # Query the database to get the corresponding IDs based on names
    student = db.query(models.Students).filter(models.Students.username == student_id).first()
    subject = db.query(models.Subjects).filter(models.Subjects.subject_name == subject_name).first()
    teacher = db.query(models.Teachers).filter(models.Teachers.id == teacher_id).first()

    # Handle cases where any of the entries is not found
    if not student:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Student not found",
            "user": user,
            "performance": None
        })
    if not subject:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Subject not found",
            "user": user,
            "performance": None
        })
    if not teacher:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Teacher not found",
            "user": user,
            "performance": None
        })

    # Retrieve the existing performance record
    performance_model = db.query(models.Performance).filter(models.Performance.id == performance_id).first()

    if not performance_model:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Performance record not found",
            "user": user,
            "performance": None
        })

    # Convert the exam_date to a datetime object
    try:
        exam_date = datetime.strptime(exam_date, "%d-%m-%Y").date()
    except ValueError:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Invalid date format. Use DD-MM-YYYY.",
            "user": user,
            "performance": performance_model  # Make sure performance is passed
        })
    
    # Update the performance record with new data
    performance_model.student_id = student.id
    performance_model.subject_id = subject.id
    performance_model.student_username = student.username  # Fix field name
    performance_model.subject_name = subject.subject_name
    performance_model.teacher_id = teacher.id
    performance_model.exam_date = exam_date  # Use the converted datetime object
    performance_model.exam_type = exam_type.lower()  # Convert exam type to lowercase
    performance_model.performance = performance

    try:
        # Commit the updated data to the database
        db.commit()
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Performance record updated successfully.",
            "performance": performance_model,
            "user": user
        })
        
    except Exception as e:
        # Rollback the transaction in case of error
        db.rollback()
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": f"Error occurred: {str(e)}",
            "performance": performance_model,  # Pass performance even in case of error
            "user": user
        })

    # Redirect on success
    return RedirectResponse(url=f'/dashboard/teacher/{teacher.id}', status_code=status.HTTP_302_FOUND)



@router.delete("/teacher/{teacher_id}/performance/{performance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance(user: user_dependency, db: db_dependency, performance_id: int = Path(gt=0)):

    # Check for authentication
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    # Query to find the performance record by ID and teacher ID
    performance_model = db.query(Performance).filter(Performance.id == performance_id).filter(Performance.teacher_id == user.get('id')).first()

    # Check if the performance record exists
    if performance_model is None:
        raise HTTPException(status_code=404, detail="Performance record not found.")

    # Perform deletion
    try:
        db.delete(performance_model)  # Delete the performance record
        db.commit()  # Commit changes to the database
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT)  # Return 204 No Content on success
    except Exception as e:
        db.rollback()  # Rollback in case of error
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")
