"""AI provider settings stored in the database."""
from datetime import datetime

from extensions import db


class AIProviderSetting(db.Model):
    """Admin-configured AI provider for Course Outline generation."""
    __tablename__ = 'ai_provider_setting'

    PROVIDER_OPENAI = 'openai'
    PROVIDER_GEMINI = 'gemini'
    PROVIDER_ANTHROPIC = 'anthropic'
    PROVIDER_DEEPSEEK = 'deepseek'

    PROVIDER_CHOICES = (
        PROVIDER_OPENAI,
        PROVIDER_GEMINI,
        PROVIDER_ANTHROPIC,
        PROVIDER_DEEPSEEK,
    )

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(30), nullable=False, default=PROVIDER_OPENAI)
    display_name = db.Column(db.String(100), nullable=True)
    api_key_encrypted = db.Column(db.Text, nullable=True)
    model_name = db.Column(db.String(100), nullable=True)
    api_base_url = db.Column(db.String(255), nullable=True)
    temperature = db.Column(db.Float, nullable=False, default=0.3)
    max_tokens = db.Column(db.Integer, nullable=False, default=8000)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AIProviderSetting {self.provider} model={self.model_name}>'

    @classmethod
    def get_active_default(cls):
        row = cls.query.filter_by(is_active=True, is_default=True).first()
        if row:
            return row
        return cls.query.filter_by(is_active=True).order_by(cls.id.asc()).first()

    @classmethod
    def default_model_for_provider(cls, provider):
        defaults = {
            cls.PROVIDER_OPENAI: 'gpt-4o-mini',
            cls.PROVIDER_GEMINI: 'gemini-1.5-flash',
            cls.PROVIDER_ANTHROPIC: 'claude-sonnet-4-6',
            cls.PROVIDER_DEEPSEEK: 'deepseek-chat',
        }
        return defaults.get(provider, 'gpt-4o-mini')


class AIOutlineGenerationJob(db.Model):
    """Multi-part async outline generation job (cPanel-friendly polling)."""
    __tablename__ = 'ai_outline_generation_job'

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    teacher_id = db.Column(db.Integer, nullable=True)
    parts_json = db.Column(db.Text, nullable=False)
    part_index = db.Column(db.Integer, nullable=False, default=0)
    partial_payload_json = db.Column(db.Text, nullable=True)
    context_summary_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def parts_list(self):
        import json
        try:
            parts = json.loads(self.parts_json or '[]')
            return [p.upper() for p in parts if p]
        except (json.JSONDecodeError, TypeError):
            return []

    def partial_payload(self):
        import json
        if not self.partial_payload_json:
            return {}
        try:
            data = json.loads(self.partial_payload_json)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_partial_payload(self, payload):
        import json
        self.partial_payload_json = json.dumps(payload or {}, ensure_ascii=False)

    def context_summary(self):
        import json
        if not self.context_summary_json:
            return {}
        try:
            data = json.loads(self.context_summary_json)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_context_summary(self, summary):
        import json
        self.context_summary_json = json.dumps(summary or {}, ensure_ascii=False, default=str)


class AIOutlineGenerationLog(db.Model):
    """Per API call log for outline generation (tokens + cost)."""
    __tablename__ = 'ai_outline_generation_log'

    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('ai_outline_generation_job.id'), nullable=True, index=True)
    session_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    part = db.Column(db.String(10), nullable=False, default='full')
    provider = db.Column(db.String(30), nullable=True)
    model_name = db.Column(db.String(100), nullable=True)
    prompt_tokens = db.Column(db.Integer, nullable=True)
    completion_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)
    estimated_cost_usd = db.Column(db.Float, nullable=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_SUCCESS)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIOutlineBatchJob(db.Model):
    """Batch outline generation across multiple class sessions."""
    __tablename__ = 'ai_outline_batch_job'

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(50), nullable=False)
    term = db.Column(db.String(50), nullable=False)
    batch = db.Column(db.String(50), nullable=True)
    items_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def items_list(self):
        import json
        try:
            data = json.loads(self.items_json or '[]')
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_items_list(self, items):
        import json
        self.items_json = json.dumps(items or [], ensure_ascii=False)
