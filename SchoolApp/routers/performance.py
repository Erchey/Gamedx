import os
import pandas as pd
from datetime import datetime



from starlette import status
from starlette.responses import RedirectResponse
from typing import Annotated, List, Optional
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from fastapi import Depends, APIRouter, Form, HTTPException, Path, Request, File, UploadFile
from starlette import status
from SchoolApp import models
from ..models import Performance, Students, Subjects, Teachers
from ..database import SessionLocal, engine
from .auth import get_current_user
from datetime import datetime, date

from fastapi.responses import HTMLResponse, JSONResponse
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
    id: Optional[int] = Field(default=None, description="ID of the performance record, automatically generated if not provided.")
    student_id: int = Field(..., description="ID of the student")
    student_username: str = Field(..., description="Username of the student")
    subject_name: str = Field(..., description="Name of the subject")
    subject_id: int = Field(..., description="ID of the subject")
    teacher_id: int = Field(..., description="ID of the teacher")
    exam_date: date = Field(..., description="Date of the exam in DD-MM-YYYY format")
    exam_type: str = Field(..., description="Type of the exam, case insensitive")
    performance: int = Field(..., gt=0, lt=101, description="Performance score between 1 and 100")


    # Override the model's initialization to ensure exam_type is stored in lowercase
    def __init__(self, **data):
        super().__init__(**data)
        self.exam_type = self.exam_type.lower()

@router.get('/student/{student_id}', response_class=HTMLResponse)
async def student_dashboard(request: Request, student_id: int, db: db_dependency):
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
async def student_dashboard(request: Request, student_id: int, db: db_dependency):
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
        "user": user,
        "msg": None
    })



@router.get('/teacher/{teacher_id}', response_class=HTMLResponse)
async def teacher_dashboard(request: Request, teacher_id: int, msg: str = None, db: Session = Depends(get_db)):
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
        "user": user,
        "msg": msg
    })



@router.get("/teacher/{teacher_id}/add-performance", response_class=HTMLResponse)
async def add_performance(request: Request, db: db_dependency):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=302)

    # Fetch the list of students, subjects, etc., that the teacher can add performance for.
    students = db.query(models.Students).all()
    subjects = db.query(models.Subjects).all()

    return templates.TemplateResponse("add-performance.html", {"request": request, "user": user, "students": students, "subjects": subjects})

@router.post("/teacher/{teacher_id}/add-performance", response_class=HTMLResponse)
async def create_performance(
    request: Request,
    exam_type: str = Form(None),
    teacher_id: int = Path(...),  
    exam_date: str = Form(None),
    performance: int = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

    csv_errors = []
    form_errors = []

    # Handle CSV file upload
    if file:
        try:
            df = pd.read_csv(file.file)
            required_columns = ['student_id', 'exam_date', 'exam_type', 'performance']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                csv_errors.append(f"Missing columns: {', '.join(missing_columns)}")

            for index, row in df.iterrows():
                student = db.query(models.Students).filter(models.Students.username == row['student_id']).first()
                teacher = db.query(models.Teachers).filter(models.Teachers.id == teacher_id).first()
                subject = db.query(models.Subjects).filter(models.Subjects.subject_name == teacher.subjects).first()

                if not student:
                    csv_errors.append(f"Invalid student_id at row {index + 1}")
                    continue

                try:
                    row['exam_date'] = datetime.strptime(row['exam_date'], "%Y-%m-%d").date()
                except ValueError:
                    csv_errors.append(f"Invalid exam_date at row {index + 1}. Use YYYY-MM-DD.")
                    continue

                if not (0 <= row['performance'] <= 100):
                    csv_errors.append(f"Performance out of range at row {index + 1}")
                    continue

                # Add the performance record
                performance_record = models.Performance(
                    student_id=student.id,
                    subject_id=subject.id,
                    student_username=student.username,
                    subject_name=subject.subject_name,
                    teacher_id=teacher.id,
                    exam_type=row['exam_type'],
                    exam_date=row['exam_date'],
                    performance=row['performance']
                )
                db.add(performance_record)

        except pd.errors.EmptyDataError:
            csv_errors.append("Uploaded CSV file is empty.")
        except Exception as e:
            csv_errors.append(f"An error occurred while processing the file: {str(e)}")

    # Handle manual form submission if no CSV file is provided
    if not file and exam_type and exam_date and performance is not None:
        student_id = Form(None)  # Ensure the student_id is available in the form
        student = db.query(models.Students).filter(models.Students.username == student_id).first()
        teacher = db.query(models.Teachers).filter(models.Teachers.id == teacher_id).first()
        subject = db.query(models.Subjects).filter(models.Subjects.subject_name == teacher.subjects).first()

        if not student:
            form_errors.append("Student not found.")

        try:
            # Add the performance record
            performance_model = models.Performance(
                student_id=student.id,
                subject_id=teacher.subject_id,
                student_username=student.username,
                subject_name=subject.subject_name,
                teacher_id=teacher.id,
                exam_type=exam_type,
                exam_date=datetime.strptime(exam_date, "%Y-%m-%d").date(),
                performance=performance
            )
            db.add(performance_model)
        except ValueError:
            form_errors.append("Invalid date format. Use YYYY-MM-DD.")

    # Check if there were any errors during CSV or form processing
    if csv_errors or form_errors:
        return templates.TemplateResponse("teachers-page.html", {
            "request": request, 
            "msg": "<br>".join(csv_errors + form_errors), 
            "user": user
        })

    # Commit to the database if no errors
    db.commit()

    # Redirect after successful submission
    return RedirectResponse(
        url=f'/dashboard/teacher/{teacher_id}?msg=Performance%20record%20added%20successfully.', 
        status_code=status.HTTP_302_FOUND
    )

@router.get("/teacher/{teacher_id}/edit-performance/{performance_id}", response_class=HTMLResponse)
async def edit_performance(request: Request, performance_id: int, db: db_dependency):
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

    # Fetch related entries
    student = db.query(models.Students).filter(models.Students.username == student_id).first()
    subject = db.query(models.Subjects).filter(models.Subjects.subject_name == subject_name).first()
    teacher = db.query(models.Teachers).filter(models.Teachers.id == teacher_id).first()

    if not student or not subject or not teacher:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Student, subject, or teacher not found.",
            "user": user,
            "performance": None
        })

    # Fetch the performance record to update
    performance_model = db.query(models.Performance).filter(models.Performance.id == performance_id).first()

    if not performance_model:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Performance record not found",
            "user": user,
            "performance": None
        })

    # Convert the exam_date to a datetime object (HTML5 date input is typically in YYYY-MM-DD)
    try:
        exam_date = datetime.strptime(exam_date, "%Y-%m-%d").date()  # Changed to the correct format
    except ValueError:
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": "Invalid date format. Use YYYY-MM-DD.",
            "user": user,
            "performance": performance_model
        })

    # Update the performance record with new data
    performance_model.student_id = student.id
    performance_model.subject_id = subject.id
    performance_model.student_username = student.username  # Fix field name
    performance_model.subject_name = subject.subject_name
    performance_model.teacher_id = teacher.id
    performance_model.exam_date = exam_date 
    performance_model.exam_type = exam_type.lower()  
    performance_model.performance = performance

    # Log updated performance model
    print(f"Updated performance: {performance_model}")

    try:
        # Commit changes to the database
        db.commit()  # No need for db.add() or db.flush() here
        
        # After successful update, redirect to the teacher dashboard
        return RedirectResponse(url=f'/dashboard/teacher/{teacher_id}', status_code=status.HTTP_302_FOUND)

    except Exception as e:
        db.rollback()
        print(f"Error occurred: {str(e)}")
        return templates.TemplateResponse("edit-performance.html", {
            "request": request,
            "msg": f"Error occurred: {str(e)}",
            "performance": performance_model,
            "user": user
        })



@router.post("/teacher/{teacher_id}/performance/{performance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance(
    user: user_dependency,
    db: db_dependency,
    performance_id: int = Path(gt=0),
    teacher_id: int = Path(gt=0)
):
    # Check for authentication
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")

    # Query to find the performance record by ID and teacher ID
    performance_model = db.query(Performance).filter(
        Performance.id == performance_id,
        Performance.teacher_id == user.get('id')
    ).first()

    # Check if the performance record exists
    if performance_model is None:
        raise HTTPException(status_code=404, detail="Performance record not found.")

    # Perform deletion
    try:
        db.delete(performance_model)  # Delete the performance record
        db.commit()  
        
        # Redirect to the teacher dashboard after successful deletion
        return RedirectResponse(url=f'/dashboard/teacher/{teacher_id}?msg=Performance%20record%20deleted%20successfully.', status_code=status.HTTP_302_FOUND)
    
    except Exception as e:
        db.rollback()  # Rollback in case of error
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")
