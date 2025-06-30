from typing import List, Dict, Tuple
import time
from sqlalchemy.orm import Session
from database import JobDescription, ConsultantProfile, Match, EmailNotification, WorkflowStatus
from models import MatchResult
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
import re
from collections import Counter

class ComparisonAgent:
    """Agent responsible for comparing job descriptions with consultant profiles"""
    
    def __init__(self):
        pass
    
    def simple_similarity(self, text1: str, text2: str) -> float:
        """
        Simple text similarity using word overlap
        """
        # Convert to lowercase and split into words
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def compare_documents(self, jd_text: str, consultant_text: str) -> float:
        """
        Compare two documents and return similarity score
        """
        return self.simple_similarity(jd_text, consultant_text)
    
    def compare_jd_with_profiles(self, db: Session, jd_id: int) -> List[Tuple[int, float]]:
        """
        Compare a job description with all available consultant profiles
        Returns list of (consultant_id, similarity_score) tuples
        """
        # Get job description
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if not jd:
            raise ValueError(f"Job description with id {jd_id} not found")
        
        # Get all available consultant profiles
        consultants = db.query(ConsultantProfile).filter(ConsultantProfile.availability == True).all()
        
        # Prepare JD text for comparison
        jd_text = f"{jd.title} {jd.description} {jd.required_skills} {jd.experience_level}"
        
        results = []
        for consultant in consultants:
            # Prepare consultant text for comparison
            consultant_text = f"{consultant.name} {consultant.skills} {consultant.experience} {consultant.years_of_experience}"
            
            # Calculate similarity
            similarity_score = self.compare_documents(jd_text, consultant_text)
            results.append((consultant.id, similarity_score))
        
        return results

class RankingAgent:
    """Agent responsible for ranking consultant profiles based on similarity scores"""
    
    def rank_profiles(self, similarity_results: List[Tuple[int, float]]) -> List[Tuple[int, float, int]]:
        """
        Rank profiles based on similarity scores
        Returns list of (consultant_id, similarity_score, rank) tuples
        """
        # Sort by similarity score in descending order
        sorted_results = sorted(similarity_results, key=lambda x: x[1], reverse=True)
        
        # Add rank
        ranked_results = []
        for rank, (consultant_id, similarity_score) in enumerate(sorted_results, 1):
            ranked_results.append((consultant_id, similarity_score, rank))
        
        return ranked_results
    
    def get_top_matches(self, ranked_results: List[Tuple[int, float, int]], top_n: int = 3) -> List[Tuple[int, float, int]]:
        """
        Get top N matches from ranked results
        """
        return ranked_results[:top_n]

class CommunicationAgent:
    """Agent responsible for sending email notifications"""
    
    def __init__(self):
        # For testing purposes, we'll use a mock email system
        # In production, use real SMTP configuration
        self.mock_mode = True  # Set to False for real emails
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
        self.sender_password = os.getenv("SENDER_PASSWORD", "your-app-password")
    
    def send_email(self, recipient_email: str, subject: str, content: str) -> bool:
        """
        Send email notification (mock mode for testing)
        """
        if self.mock_mode:
            # Mock email sending - log to console
            print("\n" + "="*60)
            print("📧 MOCK EMAIL SENT")
            print("="*60)
            print(f"From: {self.sender_email}")
            print(f"To: {recipient_email}")
            print(f"Subject: {subject}")
            print("-"*60)
            print("Content:")
            print(content)
            print("="*60)
            print("✅ Email logged successfully (Mock Mode)")
            print("="*60 + "\n")
            return True
        else:
            # Real email sending
            try:
                # Create message
                msg = MIMEMultipart()
                msg['From'] = self.sender_email
                msg['To'] = recipient_email
                msg['Subject'] = subject
                
                # Add body
                msg.attach(MIMEText(content, 'plain'))
                
                # Send email
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                text = msg.as_string()
                server.sendmail(self.sender_email, recipient_email, text)
                server.quit()
                
                return True
            except Exception as e:
                print(f"Error sending email: {e}")
                return False
    
    def send_ar_requestor_email(self, db: Session, jd_id: int, top_matches: List[MatchResult]) -> bool:
        """
        Send email to AR requestor with top matches
        """
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        
        if not jd:
            print(f"Job description with id {jd_id} not found")
            return False
        
        if not top_matches:
            subject = f"No suitable matches found for JD: {jd.title}"
            content = f"""
            Dear AR Requestor,
            
            We have completed the analysis for Job Description: {jd.title}
            
            Unfortunately, no suitable consultant matches were found for this position.
            
            Please contact the recruitment team for further assistance.
            
            Best regards,
            Recruitment System
            """
        else:
            subject = f"Top {len(top_matches)} matches found for JD: {jd.title}"
            content = f"""
            Dear AR Requestor,
            
            We have completed the analysis for Job Description: {jd.title}
            
            Here are the top {len(top_matches)} consultant matches:
            
            """
            
            for i, match in enumerate(top_matches, 1):
                content += f"""
                {i}. {match.consultant.name}
                   Email: {match.consultant.email}
                   Skills: {match.consultant.skills}
                   Experience: {match.consultant.years_of_experience} years
                   Match Score: {match.similarity_score:.2%}
                
                """
            
            content += """
            Please review these candidates and contact the recruitment team for next steps.
            
            Best regards,
            Recruitment System
            """
        
        # Create email notification record
        email_notification = EmailNotification(
            recipient_email="ar-requestor@company.com",  # In production, get from JD
            recipient_type="ar_requestor",
            subject=subject,
            content=content,
            status="pending"
        )
        db.add(email_notification)
        db.commit()
        
        # Send email
        success = self.send_email(
            email_notification.recipient_email,
            email_notification.subject,
            email_notification.content
        )
        
        # Update status
        if success:
            email_notification.status = "sent"
            email_notification.sent_at = datetime.utcnow()
        else:
            email_notification.status = "failed"
        db.commit()
        
        return success
    
    def send_recruiter_notification(self, db: Session, jd_id: int, no_matches: bool = False) -> bool:
        """
        Send notification to recruiter
        """
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        
        if not jd:
            print(f"Job description with id {jd_id} not found")
            return False
        
        if no_matches:
            subject = f"Action Required: No matches found for JD: {jd.title}"
            content = f"""
            Dear Recruiter,
            
            The system could not find suitable matches for Job Description: {jd.title}
            
            Please review the job requirements and consider:
            1. Adjusting the skill requirements
            2. Expanding the search criteria
            3. Adding new consultant profiles to the database
            
            Job Description ID: {jd_id}
            
            Best regards,
            Recruitment System
            """
        else:
            subject = f"Matches found for JD: {jd.title}"
            content = f"""
            Dear Recruiter,
            
            The system has found matches for Job Description: {jd.title}
            
            An email has been sent to the AR requestor with the top matches.
            
            Job Description ID: {jd_id}
            
            Best regards,
            Recruitment System
            """
        
        # Create email notification record
        email_notification = EmailNotification(
            recipient_email="recruiter@company.com",  # In production, get from config
            recipient_type="recruiter",
            subject=subject,
            content=content,
            status="pending"
        )
        db.add(email_notification)
        db.commit()
        
        # Send email
        success = self.send_email(
            email_notification.recipient_email,
            email_notification.subject,
            email_notification.content
        )
        
        # Update status
        if success:
            email_notification.status = "sent"
            email_notification.sent_at = datetime.utcnow()
        else:
            email_notification.status = "failed"
        db.commit()
        
        return success

class WorkflowManager:
    """Manages the overall workflow coordination between agents"""
    
    def __init__(self):
        self.comparison_agent = ComparisonAgent()
        self.ranking_agent = RankingAgent()
        self.communication_agent = CommunicationAgent()
    
    def process_jd_comparison(self, db: Session, jd_id: int) -> Dict:
        """
        Complete workflow for JD comparison and ranking
        """
        start_time = time.time()
        workflow_status = None
        
        try:
            # Step 1: Update workflow status - JD Comparison started
            workflow_status = db.query(WorkflowStatus).filter(WorkflowStatus.job_description_id == jd_id).first()
            if not workflow_status:
                workflow_status = WorkflowStatus(job_description_id=jd_id)
                db.add(workflow_status)
                db.commit()
            
            # Step 2: Compare JD with all profiles
            similarity_results = self.comparison_agent.compare_jd_with_profiles(db, jd_id)
            
            # Step 3: Rank profiles
            ranked_results = self.ranking_agent.rank_profiles(similarity_results)
            
            # Step 4: Get top matches
            top_matches_data = self.ranking_agent.get_top_matches(ranked_results, top_n=3)
            
            # Step 5: Save matches to database
            for consultant_id, similarity_score, rank in ranked_results:
                match = Match(
                    job_description_id=jd_id,
                    consultant_profile_id=consultant_id,
                    similarity_score=similarity_score,
                    rank=rank
                )
                db.add(match)
            
            db.commit()
            
            # Step 6: Prepare match results for response
            top_matches = []
            for consultant_id, similarity_score, rank in top_matches_data:
                consultant = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
                if consultant:
                    match_result = MatchResult(
                        consultant=consultant,
                        similarity_score=similarity_score,
                        rank=rank
                    )
                    top_matches.append(match_result)
            
            # Step 7: Send emails
            if top_matches:
                self.communication_agent.send_ar_requestor_email(db, jd_id, top_matches)
                self.communication_agent.send_recruiter_notification(db, jd_id, no_matches=False)
            else:
                self.communication_agent.send_recruiter_notification(db, jd_id, no_matches=True)
            
            processing_time = time.time() - start_time
            
            return {
                "job_description_id": jd_id,
                "matches": top_matches,
                "total_profiles_compared": len(similarity_results),
                "processing_time": processing_time,
                "status": "success"
            }
            
        except Exception as e:
            print(f"Error in workflow processing: {e}")
            # Update workflow status to failed if workflow_status exists
            if workflow_status:
                try:
                    # Note: We can't directly assign to SQLAlchemy columns, so we'll handle this differently
                    pass
                except:
                    pass
            db.commit()
            
            return {
                "job_description_id": jd_id,
                "error": str(e),
                "status": "failed"
            } 