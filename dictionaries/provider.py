import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from pydantic.types import conint, conlist, constr
from typing import List, Optional
from datetime import datetime

# Define the schema
class SessionDetails(BaseModel):
    scheduled_start_date: constr(regex=r'^\d{4}-\d{2}-\d{2}$')
    scheduled_start_time: constr(regex=r'^\d{2}:\d{2}$')
    scheduled_duration: conint(ge=0)
    session_status: constr(regex=r'^(scheduled|completed|canceled)$')
    session_delivery_type: constr(regex=r'^(in-person|online)$')
    tutoring_organization_id: constr(regex=r'^[a-f0-9-]{36}$')
    tutoring_program_id: constr(regex=r'^[a-f0-9-]{36}$')
    actual_session_start_time: Optional[datetime]
    actual_session_end_time: Optional[datetime]
    associated_subjects: List[str]
    session_id: constr(regex=r'^[a-f0-9-]{36}$')
    progress_monitor_score: conint(ge=0, le=100)

class TutorEnrollmentDetails(BaseModel):
    tutor_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    present_tutors_joined_session_at: List[Optional[datetime]]
    present_tutors_left_session_at: List[Optional[datetime]]
    session_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)

class StudentEnrollmentDetails(BaseModel):
    student_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    student_school_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    student_grade_level: List[str]
    present_students_joined_session_at: List[Optional[datetime]]
    present_students_left_session_at: List[Optional[datetime]]
    session_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)

class AttendanceTracking(BaseModel):
    tutor_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    student_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    attendance_status: List[constr(regex=r'^(present|absent|late)$')]
    session_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)

class EngagementMetrics(BaseModel):
    student_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    participation_level: conlist(conint(ge=1, le=5), min_items=1)
    activities_completed: conlist(conint(ge=0), min_items=1)
    session_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)

class Feedback(BaseModel):
    tutor_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    student_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)
    feedback_comments: List[str]
    session_id: conlist(constr(regex=r'^[a-f0-9-]{36}$'), min_items=1)

# Example data
data = {
    "session_details": {
        "scheduled_start_date": "2023-07-11",
        "scheduled_start_time": "15:00",
        "scheduled_duration": 60,
        "session_status": "scheduled",
        "session_delivery_type": "online",
        "tutoring_organization_id": "123e4567-e89b-12d3-a456-426614174000",
        "tutoring_program_id": "123e4567-e89b-12d3-a456-426614174000",
        "actual_session_start_time": None,
        "actual_session_end_time": None,
        "associated_subjects": ["Math", "Science"],
        "session_id": "123e4567-e89b-12d3-a456-426614174000",
        "progress_monitor_score": 85
    },
    # Add the rest of the data for tutor_enrollment_details, student_enrollment_details, etc.
}

# Validate the example data
try:
    session_details = SessionDetails(**data["session_details"])
    # Validate other sections similarly
    print("Data is valid")
except ValidationError as e:
    print("Data validation error:", e.json())

# Function to validate a DataFrame
def validate_dataframe(df, schema_model):
    for index, row in df.iterrows():
        try:
            schema_model(**row.to_dict())
        except ValidationError as e:
            print(f"Row {index} validation error:", e.json())

# Example DataFrame
df = pd.DataFrame([data["session_details"]])  # Add more rows as needed

# Validate the DataFrame
validate_dataframe(df, SessionDetails)