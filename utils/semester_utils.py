"""
Utility functions for Active Semester Management
"""
from extensions import db
from sqlalchemy import or_, and_
from blueprints.course_management.models import ActiveSemesterConfig


def get_active_semesters(batch=None):
    """
    Get all active semester configurations.
    
    Args:
        batch: Optional batch to filter by. If None, returns all active semesters.
    
    Returns:
        List of ActiveSemesterConfig objects
    """
    query = ActiveSemesterConfig.query.filter_by(is_active=True)
    
    if batch is not None:
        # Return active semester for specific batch or NULL batch (applies to all)
        query = query.filter(
            (ActiveSemesterConfig.batch == batch) | 
            (ActiveSemesterConfig.batch.is_(None))
        )
    
    return query.order_by(
        ActiveSemesterConfig.academic_session.desc(),
        ActiveSemesterConfig.year.asc(),
        ActiveSemesterConfig.term.asc()
    ).all()


def is_semester_active(academic_session, year, term, batch=None):
    """
    Check if a specific semester is active.
    
    Args:
        academic_session: Academic session string
        year: Year string
        term: Term string
        batch: Optional batch string
    
    Returns:
        Boolean indicating if the semester is active
    """
    query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True
    )
    
    if batch is not None:
        # Check for specific batch or NULL batch (applies to all)
        query = query.filter(
            (ActiveSemesterConfig.batch == batch) | 
            (ActiveSemesterConfig.batch.is_(None))
        )
    else:
        # If batch is None, check if there's an active semester for this session/year/term
        # regardless of batch
        pass
    
    return query.first() is not None


def _normalize_year_term(value):
    """Normalize year/term values for comparison (e.g., 'First' == '1st' == '1')"""
    if not value:
        return ''
    value_str = str(value).strip().lower()
    
    # Year mappings
    year_map = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second',
        '3': 'third', '3rd': 'third', 'third': 'third',
        '4': 'fourth', '4th': 'fourth', 'fourth': 'fourth',
        '5': 'fifth', '5th': 'fifth', 'fifth': 'fifth',
        'llm': 'llm'
    }
    
    # Term mappings
    term_map = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second'
    }
    
    # Try year mapping first
    normalized = year_map.get(value_str, value_str)
    if normalized != value_str:
        return normalized
    
    # Try term mapping
    normalized = term_map.get(value_str, value_str)
    return normalized


def filter_by_active_semester(query, model, batch=None, admin_override=False):
    """
    Filter a query to only include records from active semesters.
    This is a generic function that works with models that have academic_session, year, term fields.
    
    Args:
        query: SQLAlchemy query object
        model: SQLAlchemy model class
        batch: Optional batch to filter by (used for getting active semesters, not for filtering model)
        admin_override: If True, returns query without filtering (for admin users)
    
    Returns:
        Filtered query object
    """
    if admin_override:
        return query
    
    active_semesters = get_active_semesters(batch=batch)
    
    if not active_semesters:
        # If no active semester configured, return empty query
        # This prevents showing all data when no semester is marked active
        return query.filter(False)
    
    # Log active semesters for debugging
    try:
        from flask import current_app
        active_sem_info = [f"{s.academic_session}-{s.year}-{s.term}-{s.batch or 'ALL'}" for s in active_semesters]
        current_app.logger.info(f'Active semesters for filtering: {active_sem_info}')
    except:
        pass
    
    # Build SQL filter conditions with strict matching
    # Academic session: exact match required (no NULL allowance)
    # Year/Term: normalized matching for format variations
    conditions = []
    for sem in active_semesters:
        active_year_norm = _normalize_year_term(sem.year)
        active_term_norm = _normalize_year_term(sem.term)
        
        # Academic session condition: STRICT matching
        # If active semester has academic_session, require exact match (no NULL allowance)
        # If active semester has no academic_session, allow NULL but require year/term match
        if sem.academic_session:
            # Require exact academic_session match - no NULL allowance
            # This is the key fix: don't allow NULL to match
            academic_session_condition = getattr(model, 'academic_session') == sem.academic_session
        else:
            # If active semester has no academic_session, allow NULL
            academic_session_condition = getattr(model, 'academic_session').is_(None)
        
        # Year and term: normalize and match format variations
        from sqlalchemy import func
        model_year_lower = func.lower(func.trim(func.cast(getattr(model, 'year'), db.String)))
        model_term_lower = func.lower(func.trim(func.cast(getattr(model, 'term'), db.String)))
        
        # Build year condition: match normalized value and all common variations
        year_variations = [active_year_norm]
        if active_year_norm == 'first':
            year_variations.extend(['1', '1st', 'first'])
        elif active_year_norm == 'second':
            year_variations.extend(['2', '2nd', 'second'])
        elif active_year_norm == 'third':
            year_variations.extend(['3', '3rd', 'third'])
        elif active_year_norm == 'fourth':
            year_variations.extend(['4', '4th', 'fourth'])
        elif active_year_norm == 'fifth':
            year_variations.extend(['5', '5th', 'fifth'])
        elif active_year_norm == 'llm':
            year_variations.extend(['llm'])
        
        # Build term condition: match normalized value and all common variations
        term_variations = [active_term_norm]
        if active_term_norm == 'first':
            term_variations.extend(['1', '1st', 'first'])
        elif active_term_norm == 'second':
            term_variations.extend(['2', '2nd', 'second'])
        
        # Use OR to match any of the variations
        year_condition = model_year_lower.in_(year_variations)
        term_condition = model_term_lower.in_(term_variations)
        
        # Combine all conditions with AND - ALL must match
        condition = and_(
            academic_session_condition,
            year_condition,
            term_condition
        )
        
        # If semester config has a specific batch, filter by batch too
        # Note: Only apply batch filter if model has batch field
        if sem.batch and hasattr(model, 'batch'):
            condition = and_(condition, getattr(model, 'batch') == sem.batch)
        
        conditions.append(condition)
    
    if conditions:
        # Combine conditions with OR (if multiple active semesters, match any of them)
        # But each condition requires ALL fields to match (academic_session AND year AND term)
        filtered_query = query.filter(or_(*conditions))
        
        # Log filtering for debugging
        try:
            from flask import current_app
            current_app.logger.info(f'Applied active semester filter with {len(conditions)} condition(s)')
        except:
            pass
        
        return filtered_query
    
    return query.filter(False)


def get_active_semester_info(batch=None):
    """
    Get human-readable information about active semesters.
    
    Args:
        batch: Optional batch to filter by
    
    Returns:
        List of dictionaries with semester information
    """
    active_semesters = get_active_semesters(batch=batch)
    return [sem.to_dict() for sem in active_semesters]


def set_active_semester(academic_session, year, term, batch=None, activated_by=None, deactivate_others=True):
    """
    Set a semester as active. Optionally deactivate other semesters.
    
    Args:
        academic_session: Academic session string
        year: Year string
        term: Term string
        batch: Optional batch string
        activated_by: User who activated the semester
        deactivate_others: If True, deactivate all other semesters for the same batch
    
    Returns:
        ActiveSemesterConfig object or None
    """
    from datetime import datetime
    
    # Check if already exists and is active
    existing_query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True
    )
    
    if batch is not None:
        existing_query = existing_query.filter_by(batch=batch)
    else:
        existing_query = existing_query.filter(ActiveSemesterConfig.batch.is_(None))
    
    existing = existing_query.first()
    
    if existing:
        # Already active, just update activated_by and timestamp
        if activated_by:
            existing.activated_by = activated_by
        existing.activated_at = datetime.utcnow()
        db.session.commit()
        return existing
    
    # Deactivate other semesters if requested
    if deactivate_others:
        other_semesters_query = ActiveSemesterConfig.query.filter_by(is_active=True)
        
        if batch is not None:
            # Deactivate other semesters for same batch or NULL batch
            other_semesters_query = other_semesters_query.filter(
                (ActiveSemesterConfig.batch == batch) | 
                (ActiveSemesterConfig.batch.is_(None))
            )
        else:
            # If batch is None, deactivate all other semesters with NULL batch
            other_semesters_query = other_semesters_query.filter(
                ActiveSemesterConfig.batch.is_(None)
            )
        
        for sem in other_semesters_query.all():
            sem.is_active = False
            sem.deactivated_at = datetime.utcnow()
    
    # Create new active semester config
    new_config = ActiveSemesterConfig(
        academic_session=academic_session,
        year=year,
        term=term,
        batch=batch,
        is_active=True,
        activated_by=activated_by
    )
    
    db.session.add(new_config)
    db.session.commit()
    
    return new_config


def deactivate_semester(academic_session, year, term, batch=None):
    """
    Deactivate a specific semester.
    
    Args:
        academic_session: Academic session string
        year: Year string
        term: Term string
        batch: Optional batch string
    
    Returns:
        True if deactivated, False if not found
    """
    from datetime import datetime
    
    query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True
    )
    
    if batch is not None:
        query = query.filter_by(batch=batch)
    else:
        query = query.filter(ActiveSemesterConfig.batch.is_(None))
    
    semester = query.first()
    
    if semester:
        semester.is_active = False
        semester.deactivated_at = datetime.utcnow()
        db.session.commit()
        return True
    
    return False

