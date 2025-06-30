from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

# User Authentication Models
class UserBase(BaseModel):
    email: EmailStr
    role: str  # ar_requestor, recruiter, admin

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Job Description Models
class JobDescriptionBase(BaseModel):
    title: str
    description: str
    required_skills: str
    experience_level: str

class JobDescriptionCreate(JobDescriptionBase):
    pass

class JobDescription(JobDescriptionBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Consultant Profile Models
class ConsultantProfileBase(BaseModel):
    name: str
    email: EmailStr
    skills: str
    experience: str
    years_of_experience: int
    availability: bool = True

class ConsultantProfileCreate(ConsultantProfileBase):
    pass

class ConsultantProfile(ConsultantProfileBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Match Models
class MatchBase(BaseModel):
    job_description_id: int
    consultant_profile_id: int
    similarity_score: float
    rank: int

class MatchCreate(MatchBase):
    pass

class Match(MatchBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Email Notification Models
class EmailNotificationBase(BaseModel):
    recipient_email: EmailStr
    recipient_type: str
    subject: str
    content: str

class EmailNotificationCreate(EmailNotificationBase):
    pass

class EmailNotification(EmailNotificationBase):
    id: int
    status: str
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# Workflow Status Models
class WorkflowStatusBase(BaseModel):
    job_description_id: int
    jd_comparison_status: str
    profile_ranking_status: str
    email_sent_status: str

class WorkflowStatusCreate(WorkflowStatusBase):
    pass

class WorkflowStatus(WorkflowStatusBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Response Models
class MatchResult(BaseModel):
    consultant: ConsultantProfile
    similarity_score: float
    rank: int

class JobDescriptionWithMatches(BaseModel):
    job_description: JobDescription
    matches: List[MatchResult]
    workflow_status: WorkflowStatus

class ComparisonRequest(BaseModel):
    job_description_id: int

class RankingResponse(BaseModel):
    job_description_id: int
    matches: List[MatchResult]
    total_profiles_compared: int
    processing_time: float 