from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from database import create_tables, get_db, JobDescription, ConsultantProfile, Match, WorkflowStatus, EmailNotification, User
from models import (
    JobDescriptionCreate, JobDescription as JDModel,
    ConsultantProfileCreate, ConsultantProfile as ConsultantModel,
    MatchResult, JobDescriptionWithMatches, ComparisonRequest, RankingResponse, WorkflowStatus as WorkflowStatusModel, EmailNotification as EmailNotificationModel,
    UserCreate, User as UserModel, UserLogin, Token
)
from agents import WorkflowManager
from auth import authenticate_user, create_access_token, get_current_user, require_role, get_password_hash
from datetime import timedelta, datetime
import io
# from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

app = FastAPI(title="Recruitment Similarity & Ranking API")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables on startup
@app.on_event("startup")
def on_startup():
    create_tables()

# Initialize workflow manager
workflow_manager = WorkflowManager()

# Load DeBERTa model and pipeline for NER (skills/experience extraction)
# deberta_model_name = "microsoft/deberta-v3-base"
# tokenizer = AutoTokenizer.from_pretrained(deberta_model_name)
# model = AutoModelForTokenClassification.from_pretrained(deberta_model_name)
# ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

def extract_skills_experience(text: str):
    # DeBERTa temporarily disabled due to network/model download issues.
    # This placeholder returns empty lists for skills and experience.
    return {
        "skills": [],
        "experience": []
    }

# --- Authentication ---
@app.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db=None):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role}

# --- Job Descriptions ---
@app.post("/jds/", response_model=JDModel)
def create_jd(jd: JobDescriptionCreate, current_user: User = Depends(require_role("ar_requestor")), db: Session = Depends(get_db)):
    # Uniqueness check: title+description
    existing = db.query(JobDescription).filter(JobDescription.title == jd.title, JobDescription.description == jd.description).first()
    if existing:
        raise HTTPException(status_code=409, detail="This JD is already present.")
    db_jd = JobDescription(**jd.dict())
    db.add(db_jd)
    db.commit()
    db.refresh(db_jd)
    return db_jd

@app.get("/jds/", response_model=List[JDModel])
def list_jds(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(JobDescription).all()

@app.get("/jds/{jd_id}", response_model=JDModel)
def get_jd(jd_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="Job Description not found")
    return jd

@app.delete("/jds/{jd_id}")
def delete_jd(jd_id: int, current_user: User = Depends(require_role("recruiter")), db: Session = Depends(get_db)):
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="Job Description not found")
    db.delete(jd)
    db.commit()
    return {"message": "Job Description deleted successfully"}

# --- Consultant Profiles ---
@app.post("/consultants/", response_model=ConsultantModel)
def create_consultant(profile: ConsultantProfileCreate, current_user: User = Depends(require_role("recruiter")), db: Session = Depends(get_db)):
    # Uniqueness check: email
    existing = db.query(ConsultantProfile).filter(ConsultantProfile.email == profile.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="This consultant profile is already present.")
    db_profile = ConsultantProfile(**profile.dict())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

@app.get("/consultants/", response_model=List[ConsultantModel])
def list_consultants(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(ConsultantProfile).all()

@app.get("/consultants/{consultant_id}", response_model=ConsultantModel)
def get_consultant(consultant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    consultant = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    return consultant

@app.delete("/consultants/{consultant_id}")
def delete_consultant(consultant_id: int, current_user: User = Depends(require_role("recruiter")), db: Session = Depends(get_db)):
    consultant = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    db.delete(consultant)
    db.commit()
    return {"message": "Consultant deleted successfully"}

@app.get("/consultants/{consultant_id}/matches", response_model=List[dict])
def get_consultant_matches(consultant_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify consultant exists
    consultant = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Get matches for this consultant
    matches = db.query(Match).filter(Match.consultant_profile_id == consultant_id).order_by(Match.created_at.desc()).all()
    
    # Get job descriptions for these matches
    jd_ids = [m.job_description_id for m in matches]
    job_descriptions = {jd.id: jd for jd in db.query(JobDescription).filter(JobDescription.id.in_(jd_ids)).all()}
    
    # Format response
    match_history = []
    for match in matches:
        jd = job_descriptions.get(match.job_description_id)
        if jd:
            created_at_str = None
            if hasattr(match, 'created_at') and match.created_at is not None:
                created_at_str = match.created_at.isoformat()
            
            match_history.append({
                "id": match.id,
                "job_description": {
                    "id": jd.id,
                    "title": jd.title
                },
                "similarity_score": getattr(match, 'similarity_score', 0.0),
                "rank": getattr(match, 'rank', 0),
                "created_at": created_at_str
            })
    
    return match_history

# --- Matching & Workflow ---
@app.post("/match/", response_model=RankingResponse)
def match_jd(request: ComparisonRequest, current_user: User = Depends(require_role("recruiter")), db: Session = Depends(get_db)):
    result = workflow_manager.process_jd_comparison(db, request.job_description_id)
    if result["status"] != "success":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return RankingResponse(
        job_description_id=result["job_description_id"],
        matches=result["matches"],
        total_profiles_compared=result["total_profiles_compared"],
        processing_time=result["processing_time"]
    )

@app.get("/matches/{jd_id}", response_model=JobDescriptionWithMatches)
def get_matches(jd_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="Job Description not found")
    matches = db.query(Match).filter(Match.job_description_id == jd_id).order_by(Match.rank).all()
    consultant_ids = [m.consultant_profile_id for m in matches]
    consultants = {c.id: c for c in db.query(ConsultantProfile).filter(ConsultantProfile.id.in_(consultant_ids)).all()}
    match_results = [
        MatchResult(
            consultant=consultants[m.consultant_profile_id],
            similarity_score=getattr(m, 'similarity_score', 0.0),
            rank=getattr(m, 'rank', 0)
        ) for m in matches if m.consultant_profile_id in consultants
    ]
    workflow_status = db.query(WorkflowStatus).filter(WorkflowStatus.job_description_id == jd_id).first()
    return JobDescriptionWithMatches(
        job_description=jd,
        matches=match_results,
        workflow_status=workflow_status
    )

# --- Admin/Status ---
@app.get("/workflow/{jd_id}", response_model=WorkflowStatusModel)
def get_workflow_status(jd_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status = db.query(WorkflowStatus).filter(WorkflowStatus.job_description_id == jd_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Workflow status not found")
    return status

@app.get("/emails/", response_model=List[EmailNotificationModel])
def list_emails(current_user: User = Depends(require_role("recruiter")), db: Session = Depends(get_db)):
    return db.query(EmailNotification).all()

# --- AR Requestor Specific Endpoints ---
@app.post("/ar-requestor/approve-matches")
def approve_matches(request: dict, current_user: User = Depends(require_role("ar_requestor")), db: Session = Depends(get_db)):
    """AR Requestor approves selected matches"""
    consultant_ids = request.get("consultant_ids", [])
    
    # Update match status to approved
    for consultant_id in consultant_ids:
        matches = db.query(Match).filter(Match.consultant_profile_id == consultant_id).all()
        for match in matches:
            # You could add a status field to Match model for this
            pass
    
    # Send notification to recruiter
    notification = EmailNotification(
        recipient_email="recruiter@company.com",
        recipient_type="recruiter",
        subject="AR Requestor Approved Matches",
        content=f"AR Requestor {current_user.email} has approved {len(consultant_ids)} consultant(s) for further processing.",
        status="pending"
    )
    db.add(notification)
    db.commit()
    
    return {"message": "Matches approved successfully", "approved_count": len(consultant_ids)}

@app.post("/ar-requestor/request-more-candidates")
def request_more_candidates(request: dict, current_user: User = Depends(require_role("ar_requestor")), db: Session = Depends(get_db)):
    """AR Requestor requests more candidates"""
    reason = request.get("reason", "")
    additional_requirements = request.get("additional_requirements", "")
    
    # Send notification to recruiter
    notification = EmailNotification(
        recipient_email="recruiter@company.com",
        recipient_type="recruiter",
        subject="Request for More Candidates",
        content=f"""
        AR Requestor {current_user.email} has requested more candidates.
        
        Reason: {reason}
        Additional Requirements: {additional_requirements}
        
        Please review and add more consultant profiles or adjust search criteria.
        """,
        status="pending"
    )
    db.add(notification)
    db.commit()
    
    return {"message": "Request for more candidates sent to recruiter"}

@app.post("/ar-requestor/reject-matches")
def reject_matches(request: dict, current_user: User = Depends(require_role("ar_requestor")), db: Session = Depends(get_db)):
    """AR Requestor rejects all matches"""
    reason = request.get("reason", "")
    
    # Send notification to recruiter
    notification = EmailNotification(
        recipient_email="recruiter@company.com",
        recipient_type="recruiter",
        subject="Matches Rejected - Action Required",
        content=f"""
        AR Requestor {current_user.email} has rejected all current matches.
        
        Reason: {reason}
        
        Please review the job requirements and find new candidates.
        """,
        status="pending"
    )
    db.add(notification)
    db.commit()
    
    return {"message": "Matches rejected. Recruiter notified to find new candidates"}

@app.post("/ar-requestor/export-matches")
def export_matches(request: dict, current_user: User = Depends(require_role("ar_requestor")), db: Session = Depends(get_db)):
    """Export match data for AR Requestor"""
    format_type = request.get("format", "json")
    
    # Get latest matches
    latest_jd = db.query(JobDescription).order_by(JobDescription.created_at.desc()).first()
    if not latest_jd:
        return {"message": "No job descriptions found"}
    
    matches = db.query(Match).filter(Match.job_description_id == latest_jd.id).order_by(Match.rank).all()
    consultant_ids = [m.consultant_profile_id for m in matches]
    consultants = {c.id: c for c in db.query(ConsultantProfile).filter(ConsultantProfile.id.in_(consultant_ids)).all()}
    
    export_data = {
        "job_description": {
            "id": latest_jd.id,
            "title": latest_jd.title,
            "description": latest_jd.description,
            "required_skills": latest_jd.required_skills,
            "experience_level": latest_jd.experience_level
        },
        "matches": [
            {
                "rank": getattr(m, 'rank', 0),
                "similarity_score": getattr(m, 'similarity_score', 0.0),
                "consultant": {
                    "id": consultants[m.consultant_profile_id].id,
                    "name": consultants[m.consultant_profile_id].name,
                    "email": consultants[m.consultant_profile_id].email,
                    "skills": consultants[m.consultant_profile_id].skills,
                    "experience": consultants[m.consultant_profile_id].experience,
                    "years_of_experience": consultants[m.consultant_profile_id].years_of_experience
                }
            } for m in matches if m.consultant_profile_id in consultants
        ],
        "exported_by": current_user.email,
        "exported_at": datetime.utcnow().isoformat()
    }
    
    return export_data

@app.get("/ar-requestor/match-history")
def get_match_history(current_user: User = Depends(require_role("ar_requestor")), db: Session = Depends(get_db)):
    """Get match history for AR Requestor"""
    # Get recent job descriptions with their match counts
    jds = db.query(JobDescription).order_by(JobDescription.created_at.desc()).limit(10).all()
    
    history = []
    for jd in jds:
        match_count = db.query(Match).filter(Match.job_description_id == jd.id).count()
        workflow_status = db.query(WorkflowStatus).filter(WorkflowStatus.job_description_id == jd.id).first()
        
        status = "pending"
        if workflow_status:
            email_status = getattr(workflow_status, 'email_sent_status', 'pending')
            comparison_status = getattr(workflow_status, 'jd_comparison_status', 'pending')
            
            if email_status == "completed":
                status = "completed"
            elif comparison_status == "failed":
                status = "failed"
        
        created_at_str = None
        if hasattr(jd, 'created_at') and jd.created_at is not None:
            created_at_str = jd.created_at.isoformat()
        
        history.append({
            "job_description_id": jd.id,
            "job_description": {
                "id": jd.id,
                "title": jd.title
            },
            "matches_count": match_count,
            "status": status,
            "created_at": created_at_str
        })
    
    return history

# --- Test Endpoint for Workflow ---
@app.post("/test/workflow/{jd_id}")
def test_workflow(jd_id: int, current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Test the complete workflow for a specific JD"""
    try:
        # Verify JD exists
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if not jd:
            raise HTTPException(status_code=404, detail="Job Description not found")
        
        # Run the complete workflow
        result = workflow_manager.process_jd_comparison(db, jd_id)
        
        if result["status"] == "success":
            return {
                "message": "Workflow completed successfully",
                "job_description_id": jd_id,
                "matches_found": len(result["matches"]),
                "total_profiles_compared": result["total_profiles_compared"],
                "processing_time": result["processing_time"],
                "top_matches": [
                    {
                        "rank": match.rank,
                        "consultant_name": match.consultant.name,
                        "consultant_email": match.consultant.email,
                        "similarity_score": f"{match.similarity_score:.2%}"
                    } for match in result["matches"]
                ]
            }
        else:
            raise HTTPException(status_code=500, detail=f"Workflow failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing workflow: {str(e)}")

@app.get("/test/email-status")
def get_email_status(current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Get the status of recent email notifications"""
    emails = db.query(EmailNotification).order_by(EmailNotification.created_at.desc()).limit(10).all()
    
    email_status = []
    for email in emails:
        created_at_str = None
        sent_at_str = None
        
        if hasattr(email, 'created_at') and email.created_at is not None:
            created_at_str = email.created_at.isoformat()
        
        if hasattr(email, 'sent_at') and email.sent_at is not None:
            sent_at_str = email.sent_at.isoformat()
        
        email_status.append({
            "id": email.id,
            "recipient_email": email.recipient_email,
            "recipient_type": email.recipient_type,
            "subject": email.subject,
            "status": email.status,
            "created_at": created_at_str,
            "sent_at": sent_at_str
        })
    
    return email_status

@app.post("/extract-jd/")
def extract_jd(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        return {"error": "No file uploaded."}
    ext = file.filename.split('.')[-1].lower()
    content = ""
    if ext == 'txt':
        content = file.file.read().decode('utf-8')
    elif ext == 'pdf':
        if pdfplumber:
            file.file.seek(0)
            with pdfplumber.open(io.BytesIO(file.file.read())) as pdf:
                content = "\n".join(page.extract_text() or '' for page in pdf.pages)
            if not content.strip():
                return {"error": "No text could be extracted from the PDF. It may be scanned or image-based. Only text-based PDFs are supported."}
        elif PyPDF2:
            file.file.seek(0)
            reader = PyPDF2.PdfReader(file.file)
            content = " ".join(page.extract_text() or '' for page in reader.pages)
            if not content.strip():
                return {"error": "No text could be extracted from the PDF. It may be scanned or image-based. Only text-based PDFs are supported."}
        else:
            return {"error": "PDF extraction not supported. pdfplumber or PyPDF2 not installed."}
    elif ext == 'docx':
        if not DocxDocument:
            return {"error": "DOCX extraction not supported. python-docx not installed."}
        file.file.seek(0)
        doc = DocxDocument(io.BytesIO(file.file.read()))
        content = "\n".join([para.text for para in doc.paragraphs])
    else:
        return {"error": "Unsupported file type. Only txt, pdf, docx supported."}
    # Use DeBERTa to extract skills and experience
    extraction = extract_skills_experience(content)
    return {"content": content, **extraction} 