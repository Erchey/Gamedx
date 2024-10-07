from .database import Base
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship

class Students(Base):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    username = Column(String, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    hashed_password = Column(String)
    gender = Column(String)
    age = Column(Integer)
    guardian_name = Column(String)
    guardian_mail = Column(String)
    guardian_phone = Column(String)
    state_of_birth = Column(String)
    

class Teachers(Base):
    __tablename__ = 'teachers'

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    gender = Column(String)
    age = Column(Integer)
    address = Column(String)

    # Many-to-many relationship via the SubjectTeacherLink association table
    subjects = Column(String)

# Subjects table
class Subjects(Base):
    __tablename__ = 'subjects'

    id = Column(Integer, primary_key=True, index=True)
    subject_name = Column(String, unique=True)

    

# Performance table (links students, teachers, subjects, exams)
class Performance(Base):
    __tablename__ = 'performance'

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    student_username = Column(String, ForeignKey("students.username"))
    subject_name = Column(String, ForeignKey("subjects.subject_name"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    teacher_id = Column(Integer, ForeignKey("teachers.id"))
    exam_type = Column(String(50))
    exam_date = Column(Date)
    performance = Column(Integer)


class StudyHours(Base):
    __tablename__ = 'studyhours'

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Date)
    start_time = Column(Date)
    stop_time = Column(Date)
    student = Column(String)

