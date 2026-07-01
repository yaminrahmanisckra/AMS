"""PSAC Committee and Self Assessment models."""
from datetime import datetime
from extensions import db


class PsacCommittee(db.Model):
    """PSAC Committee: Head is the chair; members and ad-hoc members are teachers."""
    __tablename__ = 'psac_committee'
    id = db.Column(db.Integer, primary_key=True)
    head_teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    head_teacher = db.relationship('Teacher', foreign_keys=[head_teacher_id], backref=db.backref('psac_committee_as_head', uselist=False))
    members = db.relationship(
        'PsacCommitteeMember',
        backref='committee',
        lazy='dynamic',
        foreign_keys='PsacCommitteeMember.committee_id',
        cascade='all, delete-orphan'
    )


class PsacCommitteeMember(db.Model):
    """PSAC Committee member or ad-hoc member (teachers)."""
    __tablename__ = 'psac_committee_member'
    id = db.Column(db.Integer, primary_key=True)
    committee_id = db.Column(db.Integer, db.ForeignKey('psac_committee.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    is_adhoc = db.Column(db.Boolean, default=False, nullable=False)  # True = Ad-hoc Member
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship('Teacher', backref=db.backref('psac_memberships', lazy='dynamic'))


class SurveyLink(db.Model):
    """Public link for a survey type; Head/members generate links."""
    __tablename__ = 'survey_link'
    id = db.Column(db.Integer, primary_key=True)
    survey_type = db.Column(db.String(32), nullable=False)  # alumni, employer, faculty, non_academic, student
    access_code = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=True)
    committee_id = db.Column(db.Integer, db.ForeignKey('psac_committee.id'), nullable=True)
    window_id = db.Column(db.Integer, db.ForeignKey('operational_window.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    committee = db.relationship('PsacCommittee', backref=db.backref('survey_links', lazy='dynamic'))


class SurveyResponse(db.Model):
    """Generic response for Employer, Faculty, Non Academic, Student surveys (payload JSON)."""
    __tablename__ = 'survey_response'
    id = db.Column(db.Integer, primary_key=True)
    survey_type = db.Column(db.String(32), nullable=False)
    survey_link_id = db.Column(db.Integer, db.ForeignKey('survey_link.id'), nullable=False)
    payload = db.Column(db.Text, nullable=True)  # JSON form data
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_starred = db.Column(db.Boolean, default=False, nullable=False)

    survey_link = db.relationship('SurveyLink', backref=db.backref('responses', lazy='dynamic'))


class AlumniSurveyResponse(db.Model):
    """Response for Alumni Survey (Public). When payload is set, form follows Law Program Accreditation (Parts A–E); else legacy columns."""
    __tablename__ = 'alumni_survey_response'
    id = db.Column(db.Integer, primary_key=True)
    survey_link_id = db.Column(db.Integer, db.ForeignKey('survey_link.id'), nullable=True)  # null = legacy

    # New form (Law Program Accreditation): all data in JSON. Keys: q1..q21 (int), q22..q25 (str), optional name, batch, graduation_year
    payload = db.Column(db.Text, nullable=True)

    survey_link = db.relationship('SurveyLink', backref=db.backref('alumni_responses', lazy='dynamic'))

    # Part A: Personal Details
    name = db.Column(db.String(100), nullable=True)  # Optional
    batch = db.Column(db.String(50), nullable=True)
    graduation_year = db.Column(db.String(20), nullable=True)
    degree_completed = db.Column(db.JSON, nullable=True)  # List of degrees e.g. ["LL.B", "LL.M"]
    
    # Part A: Professional Status
    current_designation = db.Column(db.String(100), nullable=True)
    organization = db.Column(db.String(150), nullable=True)
    employment_sector = db.Column(db.String(100), nullable=True)  # Judiciary, Bar, etc.
    employment_sector_other = db.Column(db.String(100), nullable=True)
    
    # Part A: Bar Council
    is_enrolled = db.Column(db.Boolean, nullable=True)
    enrollment_time = db.Column(db.String(50), nullable=True)  # Immediately, 1-2 Years, >2 Years
    
    # Part B: Program Assessment (Ratings 1-5)
    # 1. Curriculum Balance
    curriculum_balance = db.Column(db.Integer, nullable=True)
    # 2. Knowledge & Skills
    knowledge_skills = db.Column(db.Integer, nullable=True)
    # 3. Critical Thinking
    critical_thinking = db.Column(db.Integer, nullable=True)
    # 4. Ethical Values
    ethical_values = db.Column(db.Integer, nullable=True)
    # 5. Gen Ed usefulness
    gen_ed_usefulness = db.Column(db.Integer, nullable=True)
    # 6. Assessment methods
    assessment_methods = db.Column(db.Integer, nullable=True)
    # 7. Moot Court
    moot_court = db.Column(db.Integer, nullable=True)
    # 8. Library
    library_resources = db.Column(db.Integer, nullable=True)
    # 9. Faculty Support
    faculty_support = db.Column(db.Integer, nullable=True)
    # 10. Career Counseling
    career_counseling = db.Column(db.Integer, nullable=True)
    # 11. Academic Calendar
    academic_calendar = db.Column(db.Integer, nullable=True)
    # 12. Admin Staff
    admin_staff = db.Column(db.Integer, nullable=True)
    
    # Part C: Career Progression
    # 13. Time to first job
    time_to_first_job = db.Column(db.String(50), nullable=True)
    # 14. Competitive
    job_market_competitiveness = db.Column(db.String(50), nullable=True)
    # 15. Skills (Multi-select)
    skills_acquired = db.Column(db.JSON, nullable=True)

    # Part D: Alumni Engagement & Suggestions
    # 16. Beneficial course/activity (open-ended)
    beneficial_course_activity = db.Column(db.Text, nullable=True)
    # 17. Alumni Association member (Yes/No)
    alumni_association_member = db.Column(db.Boolean, nullable=True)
    # 18. How would you like to contribute (multi-select); DB column name is 'contributions'
    contribute_to_discipline = db.Column('contributions', db.JSON, nullable=True)
    # 19. Curriculum suggestions (open-ended)
    curriculum_suggestions = db.Column(db.Text, nullable=True)
    # 20. Other comments (open-ended)
    other_comments = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_starred = db.Column(db.Boolean, default=False, nullable=False)
