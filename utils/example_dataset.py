import pandas as pd
import numpy as np
import uuid
import random
from datetime import datetime, timedelta

# Helper functions
def random_date(start, end):
    return start + timedelta(
        seconds=random.randint(0, int((end - start).total_seconds())))

def generate_uuid():
    return str(uuid.uuid4())

def generate_timestamps(start_date, duration_minutes, num_sessions):
    timestamps = []
    for _ in range(num_sessions):
        start = random_date(start_date, start_date + timedelta(days=180))
        end = start + timedelta(minutes=duration_minutes)
        timestamps.append((start, end))
    return timestamps

def normal_dist(mean, std, size):
    return np.random.normal(mean, std, size).astype(int)

def add_missing_data(df, missing_percentage_range=(10, 50)):
    for col in df.columns:
        missing_percentage = random.randint(*missing_percentage_range)
        num_missing = int(len(df) * missing_percentage / 100)
        missing_indices = random.sample(range(len(df)), num_missing)
        df.loc[missing_indices, col] = np.nan
    return df

# Main function
if __name__ == "__main__":
    # Parameters
    num_students = 1000
    min_sessions = 10
    max_sessions = 30
    mean_duration = 60  # minutes
    std_duration = 15  # minutes
    mean_score = 75
    std_score = 10

    # Generate data
    students_data = []
    sessions_data = []
    attendance_data = []
    engagement_data = []
    feedback_data = []

    subjects = ['Math', 'Science', 'English', 'History']
    statuses = ['scheduled', 'completed', 'canceled']
    delivery_types = ['in-person', 'online']
    attendance_statuses = ['present', 'absent', 'late']

    start_date = datetime.now() - timedelta(days=180)

    for student_id in range(num_students):
        student_uuid = generate_uuid()
        num_sessions = random.randint(min_sessions, max_sessions)
        duration_list = normal_dist(mean_duration, std_duration, num_sessions)
        score_list = normal_dist(mean_score, std_score, num_sessions)

        for session_num in range(num_sessions):
            session_id = generate_uuid()
            org_id = generate_uuid()
            prog_id = generate_uuid()
            subject = random.choice(subjects)
            status = random.choice(statuses)
            delivery_type = random.choice(delivery_types)
            duration = duration_list[session_num]
            score = max(0, min(100, score_list[session_num]))
            timestamps = generate_timestamps(start_date, duration, 1)[0]

            sessions_data.append({
                'session_id': session_id,
                'scheduled_start_date': timestamps[0].date(),
                'scheduled_start_time': timestamps[0].time(),
                'scheduled_duration': duration,
                'session_status': status,
                'session_delivery_type': delivery_type,
                'tutoring_organization_id': org_id,
                'tutoring_program_id': prog_id,
                'actual_session_start_time': timestamps[0],
                'actual_session_end_time': timestamps[1],
                'associated_subjects': subject,
                'progress_monitor_score': score
            })

            tutor_id = generate_uuid()
            tutor_join_time = timestamps[0] - timedelta(minutes=random.randint(0, 10))
            tutor_leave_time = timestamps[1] + timedelta(minutes=random.randint(0, 10))

            attendance_data.append({
                'tutor_id': tutor_id,
                'student_id': student_uuid,
                'attendance_status': random.choice(attendance_statuses),
                'session_id': session_id
            })

            engagement_data.append({
                'student_id': student_uuid,
                'participation_level': random.randint(1, 5),
                'activities_completed': random.randint(0, 10),
                'session_id': session_id
            })

            feedback_data.append({
                'tutor_id': tutor_id,
                'student_id': student_uuid,
                'feedback_comments': "Good session." if random.random() > 0.5 else "Needs improvement.",
                'session_id': session_id
            })

    # Convert to DataFrame
    sessions_df = pd.DataFrame(sessions_data)
    attendance_df = pd.DataFrame(attendance_data)
    engagement_df = pd.DataFrame(engagement_data)
    feedback_df = pd.DataFrame(feedback_data)

    # Introduce missing data
    sessions_df = add_missing_data(sessions_df)
    attendance_df = add_missing_data(attendance_df)
    engagement_df = add_missing_data(engagement_df)
    feedback_df = add_missing_data(feedback_df)

    # Display DataFrames
    print("Sessions Data:")
    print(sessions_df.head())

    print("\nAttendance Data:")
    print(attendance_df.head())

    print("\nEngagement Data:")
    print(engagement_df.head())

    print("\nFeedback Data:")
    print(feedback_df.head())