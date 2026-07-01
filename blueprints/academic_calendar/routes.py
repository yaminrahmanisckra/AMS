from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, Response
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta, time
from sqlalchemy import or_, and_
from collections import defaultdict
from extensions import db
from .models import AcademicCalendarEvent, BatchCustomEvent
from user_models import User
from role_utils import parse_roles, has_teacher_privileges
from utils.window_utils import (
    query_for_window, stamp_window_id, filter_by_window_sessions,
    get_or_404_for_window,
)
from blueprints.class_management.models import Session, Teacher, ClassStudent
from blueprints.student_management.models import Student
from . import academic_calendar_bp


def _batch_events_query():
    """Batch custom events scoped via parent class session window."""
    return filter_by_window_sessions(BatchCustomEvent.query, BatchCustomEvent.session_id)


def _get_batch_event_or_404(event_id):
    return _batch_events_query().filter_by(id=event_id).first_or_404()

def can_edit_calendar():
    """Check if current user can edit calendar (Head or Teaching Assistant)"""
    if not current_user.is_authenticated:
        return False
    roles = set(parse_roles(current_user.role))
    if getattr(current_user, 'active_role', None):
        roles = set(parse_roles(current_user.active_role))
    return 'head' in roles or 'teaching_assistant' in roles


def _normalize_semester_label(label):
    return str(label or '').strip()


def _extract_semester_context(event):
    """Extract Year/Term/Session metadata from semester event title/description."""
    context = {'year': '', 'term': '', 'session': ''}
    description = str(getattr(event, 'description', '') or '')
    for raw_line in description.splitlines():
        line = raw_line.strip()
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        normalized_key = key.strip().lower()
        normalized_value = value.strip()
        if normalized_key == 'year':
            context['year'] = normalized_value
        elif normalized_key == 'term':
            context['term'] = normalized_value
        elif normalized_key in ('academic session', 'session'):
            context['session'] = normalized_value

    title = str(getattr(event, 'title', '') or '')
    if '(' in title and ')' in title and title.rfind(')') > title.rfind('('):
        inside = title[title.rfind('(') + 1:title.rfind(')')]
        for part in [p.strip() for p in inside.split(',') if p.strip()]:
            lower_part = part.lower()
            if lower_part.startswith('year '):
                context['year'] = context['year'] or part[5:].strip()
            elif lower_part.startswith('term '):
                context['term'] = context['term'] or part[5:].strip()
            elif lower_part.startswith('session '):
                context['session'] = context['session'] or part[8:].strip()
    return context


def _build_semester_grouped_event(event_type, grouped_events, event_day):
    """Create one combined display/export item from multiple semester events."""
    if not grouped_events:
        return None

    default_title = 'Semester Start' if event_type == 'semester_start' else 'Semester End'
    first_title = _normalize_semester_label(getattr(grouped_events[0], 'title', ''))
    base_title = first_title.split(' (', 1)[0].strip() if first_title else default_title
    if not base_title:
        base_title = default_title

    context_set = set()
    for event in grouped_events:
        ctx = _extract_semester_context(event)
        context_set.add((ctx.get('year', ''), ctx.get('term', ''), ctx.get('session', '')))

    sorted_contexts = sorted(
        context_set,
        key=lambda x: (_normalize_semester_label(x[2]), _normalize_semester_label(x[0]), _normalize_semester_label(x[1]))
    )
    context_lines = []
    for year_value, term_value, session_value in sorted_contexts:
        pieces = []
        if year_value:
            pieces.append(f'Year: {year_value}')
        if term_value:
            pieces.append(f'Term: {term_value}')
        if session_value:
            pieces.append(f'Academic Session: {session_value}')
        if pieces:
            context_lines.append(' | '.join(pieces))

    summary_title = f"{base_title} ({len(grouped_events)})" if len(grouped_events) > 1 else base_title
    summary_description = '\n'.join(context_lines)
    latest_updated = max(
        [getattr(event, 'updated_at', None) for event in grouped_events if getattr(event, 'updated_at', None)],
        default=None
    )
    earliest_created = min(
        [getattr(event, 'created_at', None) for event in grouped_events if getattr(event, 'created_at', None)],
        default=None
    )

    return {
        'id': f"semester_group_{event_type}_{event_day.strftime('%Y%m%d')}",
        'title': summary_title,
        'description': summary_description,
        'event_date': event_day,
        'end_date': event_day,
        'event_type': event_type,
        'is_grouped_semester': True,
        'group_count': len(grouped_events),
        'contexts': context_lines,
        'source_event_ids': [event.id for event in grouped_events],
        'created_at': earliest_created,
        'updated_at': latest_updated,
    }


def _merge_semester_events_for_day(day_events, event_day):
    """Merge same-day semester start/end entries into single entries."""
    semester_buckets = defaultdict(list)
    preserved_items = []

    for item in day_events:
        if isinstance(item, dict):
            preserved_items.append(item)
            continue
        event_type = getattr(item, 'event_type', None)
        if event_type in ('semester_start', 'semester_end'):
            semester_buckets[event_type].append(item)
        else:
            preserved_items.append(item)

    for semester_type in ('semester_start', 'semester_end'):
        grouped_events = semester_buckets.get(semester_type, [])
        if not grouped_events:
            continue
        if len(grouped_events) == 1:
            preserved_items.append(grouped_events[0])
            continue
        grouped_item = _build_semester_grouped_event(semester_type, grouped_events, event_day)
        if grouped_item:
            preserved_items.append(grouped_item)

    return preserved_items


def _merge_upcoming_semester_events(upcoming_events):
    """Merge duplicate semester start/end rows in the upcoming list."""
    grouped = defaultdict(list)
    preserved = []

    for event_date, event in upcoming_events:
        if isinstance(event, dict):
            preserved.append((event_date, event))
            continue
        event_type = getattr(event, 'event_type', None)
        if event_type in ('semester_start', 'semester_end'):
            grouped[(event.event_date, event_type)].append(event)
        else:
            preserved.append((event_date, event))

    for (event_day, event_type), grouped_events in grouped.items():
        if len(grouped_events) == 1:
            preserved.append((event_day, grouped_events[0]))
            continue
        grouped_item = _build_semester_grouped_event(event_type, grouped_events, event_day)
        if grouped_item:
            preserved.append((event_day, grouped_item))

    preserved.sort(key=lambda x: x[0])
    return preserved

@academic_calendar_bp.route('/')
@login_required
def index():
    """Display academic calendar with events and holidays"""
    try:
        # Ensure table exists - try to create if it doesn't
        try:
            # Quick check if table exists by trying a simple query
            query_for_window(AcademicCalendarEvent).limit(1).all()
        except Exception as check_error:
            error_str = str(check_error).lower()
            if 'no such table' in error_str or 'does not exist' in error_str or 'relation' in error_str:
                # Table doesn't exist, create it
                try:
                    current_app.logger.info("Creating academic_calendar_event table...")
                    db.create_all()
                    current_app.logger.info("✓ Table 'academic_calendar_event' created successfully!")
                except Exception as create_error:
                    current_app.logger.error(f"Failed to create table: {create_error}", exc_info=True)
                    flash('Database table creation failed. Please run: python3 create_academic_calendar_table.py', 'error')
                    return render_template('academic_calendar/index.html', 
                                         year=datetime.now().year, 
                                         month=datetime.now().month,
                                         events_by_date={},
                                         can_edit=can_edit_calendar(),
                                         current_date=date.today(),
                                         upcoming_events=[],
                                         view_type='month',
                                         student_batch=None,
                                         parse_roles=parse_roles,
                                         has_teacher_privileges=has_teacher_privileges)
        
        # Get view type (year or month), default to month
        view_type = request.args.get('view', 'month')
        
        # Get current year and month from request or use current date
        year = request.args.get('year', type=int) or datetime.now().year
        month = request.args.get('month', type=int) or datetime.now().month
        
        # Get all events for the year
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        try:
            events = query_for_window(AcademicCalendarEvent).filter(
                or_(
                    and_(
                        AcademicCalendarEvent.event_date >= start_date,
                        AcademicCalendarEvent.event_date <= end_date
                    ),
                    and_(
                        AcademicCalendarEvent.end_date.isnot(None),
                        AcademicCalendarEvent.end_date >= start_date,
                        AcademicCalendarEvent.event_date <= end_date
                    )
                )
            ).order_by(AcademicCalendarEvent.event_date.asc()).all()
            
            current_app.logger.info(f"Found {len(events)} events for year {year}")
        except Exception as db_error:
            current_app.logger.error(f"Database error querying events: {db_error}", exc_info=True)
            error_str = str(db_error).lower()
            # If end_date column doesn't exist, query without it
            if 'no such column' in error_str or 'end_date' in error_str:
                try:
                    current_app.logger.warning("end_date column missing, querying without it")
                    events = query_for_window(AcademicCalendarEvent).filter(
                        AcademicCalendarEvent.event_date >= start_date,
                        AcademicCalendarEvent.event_date <= end_date
                    ).order_by(AcademicCalendarEvent.event_date.asc()).all()
                    current_app.logger.info(f"Found {len(events)} events (without end_date filter)")
                except Exception as retry_error:
                    current_app.logger.error(f"Retry query also failed: {retry_error}", exc_info=True)
                    events = []
            else:
                events = []
        
        # Create event map by date (handle date ranges)
        events_by_date = {}
        for event in events:
            try:
                # If event has an end_date, add it to all dates in the range
                event_end_date = getattr(event, 'end_date', None)
                if event_end_date and event_end_date > event.event_date:
                    current_date = event.event_date
                    while current_date <= event_end_date:
                        date_str = current_date.strftime('%Y-%m-%d')
                        if date_str not in events_by_date:
                            events_by_date[date_str] = []
                        events_by_date[date_str].append(event)
                        current_date += timedelta(days=1)
                else:
                    # Single day event
                    event_date_str = event.event_date.strftime('%Y-%m-%d')
                    if event_date_str not in events_by_date:
                        events_by_date[event_date_str] = []
                    events_by_date[event_date_str].append(event)
            except Exception as event_error:
                current_app.logger.error(f"Error processing event {event.id}: {event_error}", exc_info=True)
                # Still add the event for its start date as fallback
                try:
                    event_date_str = event.event_date.strftime('%Y-%m-%d')
                    if event_date_str not in events_by_date:
                        events_by_date[event_date_str] = []
                    events_by_date[event_date_str].append(event)
                except:
                    pass
        
        current_app.logger.info(f"Created events_by_date with {len(events_by_date)} dates")
        
        # Get recurring weekly holidays (Friday and Saturday)
        recurring_holidays = []
        current_date = date(year, 1, 1)
        while current_date.year == year:
            # Friday is weekday 4, Saturday is weekday 5 (Monday=0)
            if current_date.weekday() == 4:  # Friday
                recurring_holidays.append({
                    'date': current_date,
                    'title': 'শুক্রবার (ছুটি)',
                    'type': 'holiday',
                    'is_weekly': True
                })
            elif current_date.weekday() == 5:  # Saturday
                recurring_holidays.append({
                    'date': current_date,
                    'title': 'শনিবার (ছুটি)',
                    'type': 'holiday',
                    'is_weekly': True
                })
            current_date += timedelta(days=1)
        
        # Merge recurring holidays with events
        for holiday in recurring_holidays:
            holiday_date_str = holiday['date'].strftime('%Y-%m-%d')
            if holiday_date_str not in events_by_date:
                events_by_date[holiday_date_str] = []
            # Add recurring holiday if not already in events
            events_by_date[holiday_date_str].insert(0, holiday)
        
        # Add batch-specific custom events for students and teachers
        batch_events_by_date = {}
        student_batch = None
        if current_user.is_authenticated:
            roles = set(parse_roles(current_user.role))
            batch_events = []
            
            if 'student' in roles:
                # Get student's batch
                student = Student.query.filter_by(student_id=current_user.username).first()
                if student and student.batch:
                    student_batch = student.batch
                    # Get all batch events for this student's batch
                    batch_events = _batch_events_query().filter_by(batch=student_batch).filter(
                        or_(
                            and_(
                                BatchCustomEvent.event_date >= start_date,
                                BatchCustomEvent.event_date <= end_date
                            )
                        )
                    ).order_by(BatchCustomEvent.event_date.asc()).all()
            
            elif has_teacher_privileges(current_user):
                # Teachers see all batch events they created
                batch_events = _batch_events_query().filter_by(created_by_id=current_user.id).filter(
                    or_(
                        and_(
                            BatchCustomEvent.event_date >= start_date,
                            BatchCustomEvent.event_date <= end_date
                        )
                    )
                ).order_by(BatchCustomEvent.event_date.asc()).all()
            
            # Add batch events to events_by_date
            for batch_event in batch_events:
                event_date_str = batch_event.event_date.strftime('%Y-%m-%d')
                if event_date_str not in events_by_date:
                    events_by_date[event_date_str] = []
                # Mark as batch event for display
                events_by_date[event_date_str].append({
                    'id': f'batch_{batch_event.id}',
                    'title': batch_event.title,
                    'description': batch_event.description,
                    'event_date': batch_event.event_date,
                    'event_time': batch_event.event_time,
                    'event_type': batch_event.event_type,
                    'location': batch_event.location,
                    'course_code': batch_event.session.course_code if batch_event.session else None,
                    'course_name': batch_event.session.course_name if batch_event.session else None,
                    'is_batch_event': True,
                    'batch': batch_event.batch
                })

        # Merge same-day duplicate semester start/end entries into one visible row
        for day_str, day_events in list(events_by_date.items()):
            try:
                event_day = datetime.strptime(day_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            events_by_date[day_str] = _merge_semester_events_for_day(day_events, event_day)
        
        can_edit = can_edit_calendar()
        
        # Prepare upcoming events list (sorted by date)
        upcoming_events_list = []
        today = date.today()
        for event in events:
            if event.event_date >= today:
                upcoming_events_list.append((event.event_date, event))
        
        # Add batch events to upcoming events list
        if current_user.is_authenticated:
            roles = set(parse_roles(current_user.role))
            batch_events_for_upcoming = []
            
            if 'student' in roles:
                student = Student.query.filter_by(student_id=current_user.username).first()
                if student and student.batch:
                    batch_events_for_upcoming = _batch_events_query().filter_by(batch=student.batch).filter(
                        BatchCustomEvent.event_date >= today
                    ).order_by(BatchCustomEvent.event_date.asc()).all()
            elif has_teacher_privileges(current_user):
                # Teachers see their created batch events
                batch_events_for_upcoming = _batch_events_query().filter_by(created_by_id=current_user.id).filter(
                    BatchCustomEvent.event_date >= today
                ).order_by(BatchCustomEvent.event_date.asc()).all()
            
            # Convert batch events to dict format for upcoming list
            for batch_event in batch_events_for_upcoming:
                upcoming_events_list.append((batch_event.event_date, {
                    'id': f'batch_{batch_event.id}',
                    'title': batch_event.title,
                    'description': batch_event.description,
                    'event_date': batch_event.event_date,
                    'event_time': batch_event.event_time,
                    'event_type': batch_event.event_type,
                    'location': batch_event.location,
                    'course_code': batch_event.session.course_code if batch_event.session else None,
                    'course_name': batch_event.session.course_name if batch_event.session else None,
                    'is_batch_event': True,
                    'batch': batch_event.batch
                }))
        
        upcoming_events_list.sort(key=lambda x: x[0])
        upcoming_events_list = _merge_upcoming_semester_events(upcoming_events_list)
        
        return render_template(
            'academic_calendar/index.html',
            year=year,
            month=month,
            events_by_date=events_by_date,
            can_edit=can_edit,
            current_date=today,
            upcoming_events=upcoming_events_list[:10],
            view_type=view_type,
            student_batch=student_batch,
            parse_roles=parse_roles,
            has_teacher_privileges=has_teacher_privileges
        )
    except Exception as e:
        current_app.logger.error(f"Error loading academic calendar: {e}", exc_info=True)
        error_str = str(e).lower()
        # Check if it's a database/table issue
        if 'no such table' in error_str or 'does not exist' in error_str or 'relation' in error_str:
            try:
                # Try to create the table
                db.create_all()
                current_app.logger.info("Created academic_calendar_event table automatically")
                flash('Calendar table created. Please refresh the page.', 'success')
                return redirect(url_for('academic_calendar.index'))
            except Exception as create_error:
                current_app.logger.error(f"Failed to create table: {create_error}", exc_info=True)
                flash('Database table not found. Please run: python3 create_academic_calendar_table.py', 'warning')
                # Still render the page with empty data instead of redirecting
                return render_template('academic_calendar/index.html', 
                                     year=datetime.now().year, 
                                     month=datetime.now().month,
                                     events_by_date={},
                                     can_edit=can_edit_calendar(),
                                     current_date=date.today(),
                                     upcoming_events=[],
                                 view_type='month',
                                 student_batch=None,
                                 parse_roles=parse_roles,
                                 has_teacher_privileges=has_teacher_privileges)
        else:
            # For other errors, still try to show the calendar with empty data
            flash(f'Error loading calendar: {str(e)[:100]}. Showing empty calendar.', 'warning')
            return render_template('academic_calendar/index.html', 
                                 year=datetime.now().year, 
                                 month=datetime.now().month,
                                 events_by_date={},
                                 can_edit=can_edit_calendar(),
                                 current_date=date.today(),
                                 upcoming_events=[],
                                 view_type='month',
                                 student_batch=None,
                                 parse_roles=parse_roles,
                                 has_teacher_privileges=has_teacher_privileges)

@academic_calendar_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_event():
    """Add a new calendar event"""
    if not can_edit_calendar():
        flash('You do not have permission to edit the calendar.', 'danger')
        return redirect(url_for('academic_calendar.index'))
    
    # Get unique years, terms, and academic sessions from Session table for dropdowns
    try:
        unique_years = db.session.query(Session.year).distinct().order_by(Session.year.desc()).all()
        years_list = [y[0] for y in unique_years if y[0]]
        
        unique_terms = db.session.query(Session.term).distinct().order_by(Session.term).all()
        terms_list = [t[0] for t in unique_terms if t[0]]
        
        unique_sessions = db.session.query(Session.academic_session).distinct().filter(
            Session.academic_session.isnot(None)
        ).order_by(Session.academic_session.desc()).all()
        academic_sessions_list = [s[0] for s in unique_sessions if s[0]]
    except Exception as e:
        current_app.logger.warning(f"Error fetching session data: {e}")
        years_list = []
        terms_list = []
        academic_sessions_list = []
    
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            event_date_str = request.form.get('event_date', '').strip()
            event_type = request.form.get('event_type', 'event').strip()
            
            if not title or not event_date_str:
                flash('Title and date are required.', 'error')
                return redirect(url_for('academic_calendar.add_event'))
            
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid start date format.', 'error')
                return redirect(url_for('academic_calendar.add_event'))
            
            # Handle end date (optional)
            end_date = None
            end_date_str = request.form.get('end_date', '').strip()
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    if end_date < event_date:
                        flash('End date must be after or equal to start date.', 'error')
                        return redirect(url_for('academic_calendar.add_event'))
                except ValueError:
                    flash('Invalid end date format.', 'error')
                    return redirect(url_for('academic_calendar.add_event'))
            
            # Handle semester start/end with multiple sessions, years, and terms
            if event_type in ['semester_start', 'semester_end']:
                selected_years = request.form.getlist('selected_years')
                selected_terms = request.form.getlist('selected_terms')
                selected_academic_sessions = request.form.getlist('selected_academic_sessions')
                
                # If no selections, create a single event
                if not selected_years and not selected_terms and not selected_academic_sessions:
                    event = AcademicCalendarEvent(
                        title=title,
                        description=description or None,
                        event_date=event_date,
                        end_date=end_date,
                        event_type=event_type,
                        created_by_id=current_user.id
                    )
                    stamp_window_id(event)
                    db.session.add(event)
                else:
                    # Create events for each combination
                    events_created = 0
                    
                    # If no specific selections, use all combinations
                    if not selected_years:
                        selected_years = years_list
                    if not selected_terms:
                        selected_terms = terms_list
                    if not selected_academic_sessions:
                        selected_academic_sessions = academic_sessions_list
                    
                    # Create events for each year/term/session combination
                    for year in selected_years:
                        for term in selected_terms:
                            for academic_session in selected_academic_sessions:
                                # Build title with year, term, and session info
                                event_title = f"{title}"
                                if year or term or academic_session:
                                    parts = []
                                    if year:
                                        parts.append(f"Year {year}")
                                    if term:
                                        parts.append(f"Term {term}")
                                    if academic_session:
                                        parts.append(f"Session {academic_session}")
                                    if parts:
                                        event_title += f" ({', '.join(parts)})"
                                
                                # Build description
                                event_description = description or ''
                                if year or term or academic_session:
                                    desc_parts = []
                                    if year:
                                        desc_parts.append(f"Year: {year}")
                                    if term:
                                        desc_parts.append(f"Term: {term}")
                                    if academic_session:
                                        desc_parts.append(f"Academic Session: {academic_session}")
                                    if desc_parts:
                                        if event_description:
                                            event_description += "\n\n"
                                        event_description += "\n".join(desc_parts)
                                
                                event = AcademicCalendarEvent(
                                    title=event_title,
                                    description=event_description or None,
                                    event_date=event_date,
                                    end_date=end_date,
                                    event_type=event_type,
                                    created_by_id=current_user.id
                                )
                                stamp_window_id(event)
                                db.session.add(event)
                                events_created += 1
                    
                    if events_created > 0:
                        flash(f'{events_created} event(s) created successfully for selected combinations.', 'success')
                    else:
                        flash('No events created. Please select at least one year, term, or academic session.', 'warning')
            else:
                # Regular event (not semester start/end)
                event = AcademicCalendarEvent(
                    title=title,
                    description=description or None,
                    event_date=event_date,
                    end_date=end_date,
                    event_type=event_type,
                    created_by_id=current_user.id
                )
                stamp_window_id(event)
                db.session.add(event)
            
            try:
                db.session.commit()
                current_app.logger.info(f"Event(s) added successfully")
                if event_type not in ['semester_start', 'semester_end']:
                    flash('Event added successfully.', 'success')
                return redirect(url_for('academic_calendar.index'))
            except Exception as commit_error:
                db.session.rollback()
                current_app.logger.error(f"Error committing event: {commit_error}", exc_info=True)
                raise
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding calendar event: {e}", exc_info=True)
            error_str = str(e).lower()
            # Check if it's a missing column error
            if 'no such column' in error_str or 'end_date' in error_str:
                try:
                    # Try to add the column or recreate table
                    db.create_all()
                    current_app.logger.info("Updated academic_calendar_event table with end_date column")
                    flash('Database updated. Please try adding the event again.', 'success')
                except Exception as create_error:
                    current_app.logger.error(f"Failed to update table: {create_error}", exc_info=True)
                    flash('Database table needs update. Please run: python3 create_academic_calendar_table.py', 'error')
            else:
                flash(f'Error adding event: {str(e)[:100]}. Please try again.', 'error')
            return redirect(url_for('academic_calendar.add_event'))
    
    return render_template('academic_calendar/add_event.html',
                         years_list=years_list,
                         terms_list=terms_list,
                         academic_sessions_list=academic_sessions_list)

@academic_calendar_bp.route('/api/sessions-years-terms', methods=['POST'])
@login_required
def api_sessions_years_terms():
    """API endpoint to get available years and terms for selected academic sessions"""
    try:
        data = request.get_json()
        selected_sessions = data.get('sessions', [])
        
        if not selected_sessions:
            # If no sessions selected, return all years and terms
            try:
                unique_years = db.session.query(Session.year).distinct().order_by(Session.year.desc()).all()
                years_list = [y[0] for y in unique_years if y[0]]
                
                unique_terms = db.session.query(Session.term).distinct().order_by(Session.term).all()
                terms_list = [t[0] for t in unique_terms if t[0]]
                
                return jsonify({
                    'success': True,
                    'years': years_list,
                    'terms': terms_list
                })
            except Exception as e:
                current_app.logger.error(f"Error fetching all years/terms: {e}")
                return jsonify({
                    'success': True,
                    'years': [],
                    'terms': []
                })
        
        # Get years and terms for selected sessions
        try:
            sessions_query = query_for_window(Session).filter(
                Session.academic_session.in_(selected_sessions)
            )
            
            unique_years = db.session.query(Session.year).filter(
                Session.academic_session.in_(selected_sessions)
            ).distinct().order_by(Session.year.desc()).all()
            years_list = [y[0] for y in unique_years if y[0]]
            
            unique_terms = db.session.query(Session.term).filter(
                Session.academic_session.in_(selected_sessions)
            ).distinct().order_by(Session.term).all()
            terms_list = [t[0] for t in unique_terms if t[0]]
            
            return jsonify({
                'success': True,
                'years': years_list,
                'terms': terms_list
            })
        except Exception as e:
            current_app.logger.error(f"Error fetching years/terms for sessions: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}',
                'years': [],
                'terms': []
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in api_sessions_years_terms: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'years': [],
            'terms': []
        }), 500

@academic_calendar_bp.route('/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """Edit an existing calendar event"""
    if not can_edit_calendar():
        flash('You do not have permission to edit the calendar.', 'danger')
        return redirect(url_for('academic_calendar.index'))
    
    event = get_or_404_for_window(AcademicCalendarEvent, event_id)
    
    if request.method == 'POST':
        try:
            event.title = request.form.get('title', '').strip()
            event.description = request.form.get('description', '').strip()
            event_date_str = request.form.get('event_date', '').strip()
            event.event_type = request.form.get('event_type', 'event').strip()
            
            if not event.title or not event_date_str:
                flash('Title and date are required.', 'error')
                return redirect(url_for('academic_calendar.edit_event', event_id=event_id))
            
            try:
                event.event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid start date format.', 'error')
                return redirect(url_for('academic_calendar.edit_event', event_id=event_id))
            
            # Handle end date (optional)
            end_date_str = request.form.get('end_date', '').strip()
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    if end_date < event.event_date:
                        flash('End date must be after or equal to start date.', 'error')
                        return redirect(url_for('academic_calendar.edit_event', event_id=event_id))
                    event.end_date = end_date
                except ValueError:
                    flash('Invalid end date format.', 'error')
                    return redirect(url_for('academic_calendar.edit_event', event_id=event_id))
            else:
                event.end_date = None
            
            db.session.commit()
            
            flash('Event updated successfully.', 'success')
            return redirect(url_for('academic_calendar.index'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating calendar event: {e}", exc_info=True)
            flash('Error updating event. Please try again.', 'error')
            return redirect(url_for('academic_calendar.edit_event', event_id=event_id))
    
    return render_template('academic_calendar/edit_event.html', event=event)

@academic_calendar_bp.route('/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    """Delete a calendar event"""
    if not can_edit_calendar():
        return jsonify({'success': False, 'message': 'You do not have permission to delete events.'}), 403
    
    try:
        event = get_or_404_for_window(AcademicCalendarEvent, event_id)
        db.session.delete(event)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Event deleted successfully.'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting calendar event: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error deleting event.'}), 500

@academic_calendar_bp.route('/api/events')
@login_required
def api_events():
    """API endpoint to get events for a date range"""
    try:
        start_date_str = request.args.get('start')
        end_date_str = request.args.get('end')
        
        if not start_date_str or not end_date_str:
            return jsonify({'error': 'Start and end dates are required'}), 400
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        events = query_for_window(AcademicCalendarEvent).filter(
            AcademicCalendarEvent.event_date >= start_date,
            AcademicCalendarEvent.event_date <= end_date
        ).order_by(AcademicCalendarEvent.event_date.asc()).all()
        
        # Add recurring Friday/Saturday holidays
        result = []
        current_date = start_date
        while current_date <= end_date:
            # Friday is weekday 4, Saturday is weekday 5
            if current_date.weekday() == 4:  # Friday
                result.append({
                    'id': f'weekly_friday_{current_date}',
                    'title': 'শুক্রবার (ছুটি)',
                    'start': current_date.strftime('%Y-%m-%d'),
                    'type': 'holiday',
                    'is_weekly': True
                })
            elif current_date.weekday() == 5:  # Saturday
                result.append({
                    'id': f'weekly_saturday_{current_date}',
                    'title': 'শনিবার (ছুটি)',
                    'start': current_date.strftime('%Y-%m-%d'),
                    'type': 'holiday',
                    'is_weekly': True
                })
            current_date += timedelta(days=1)
        
        # Add regular events
        for event in events:
            result.append({
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'start': event.event_date.strftime('%Y-%m-%d'),
                'type': event.event_type,
                'is_weekly': False
            })
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error fetching calendar events: {e}", exc_info=True)
        return jsonify({'error': 'Error fetching events'}), 500

@academic_calendar_bp.route('/export/<int:event_id>.ics')
@login_required
def export_event_ics(event_id):
    """Export a single event as ICS file"""
    try:
        event = get_or_404_for_window(AcademicCalendarEvent, event_id)
        
        # Generate ICS content
        ics_content = generate_ics_for_event(event)
        
        # Return as downloadable file
        response = Response(ics_content, mimetype='text/calendar')
        response.headers['Content-Disposition'] = f'attachment; filename="academic_event_{event_id}.ics"'
        return response
    except Exception as e:
        current_app.logger.error(f"Error exporting event ICS: {e}", exc_info=True)
        flash('Error exporting event.', 'error')
        return redirect(url_for('academic_calendar.index'))

@academic_calendar_bp.route('/export/all.ics')
@login_required
def export_all_ics():
    """Export all events as ICS file (calendar feed)"""
    try:
        # Get all events
        events = query_for_window(AcademicCalendarEvent).order_by(AcademicCalendarEvent.event_date.asc()).all()
        
        # Generate ICS content for all events
        ics_content = generate_ics_calendar(events, include_weekly_holidays=False)
        
        # Return as downloadable file or calendar feed
        response = Response(ics_content, mimetype='text/calendar')
        response.headers['Content-Disposition'] = 'attachment; filename="academic_calendar.ics"'
        # Also allow subscription
        response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
        return response
    except Exception as e:
        current_app.logger.error(f"Error exporting calendar ICS: {e}", exc_info=True)
        flash('Error exporting calendar.', 'error')
        return redirect(url_for('academic_calendar.index'))

def generate_ics_for_event(event):
    """Generate ICS content for a single event"""
    # Format dates for ICS (YYYYMMDDTHHMMSSZ format)
    dtstart = event.event_date.strftime('%Y%m%d')
    dtend = event.end_date.strftime('%Y%m%d') if event.end_date else event.event_date.strftime('%Y%m%d')
    
    # If end_date exists and is different, add one day to end_date for all-day events
    if event.end_date and event.end_date > event.event_date:
        # For all-day events spanning multiple days, end date should be exclusive
        end_date_calc = event.end_date + timedelta(days=1)
        dtend = end_date_calc.strftime('%Y%m%d')
    else:
        # Single day event - end date is next day
        end_date_calc = event.event_date + timedelta(days=1)
        dtend = end_date_calc.strftime('%Y%m%d')
    
    # Generate unique ID
    uid = f"academic-event-{event.id}@khulna-university"
    
    # Escape text for ICS format
    def escape_ics_text(text):
        if not text:
            return ''
        # Replace special characters
        text = str(text).replace('\\', '\\\\')
        text = text.replace(',', '\\,')
        text = text.replace(';', '\\;')
        text = text.replace('\n', '\\n')
        return text
    
    title = escape_ics_text(event.title)
    description = escape_ics_text(event.description or '')
    
    # Build ICS content
    ics_lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Khulna University//Academic Calendar//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTART;VALUE=DATE:{dtstart}',
        f'DTEND;VALUE=DATE:{dtend}',
        f'SUMMARY:{title}',
        f'DESCRIPTION:{description}',
        f'DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
        f'CREATED:{event.created_at.strftime("%Y%m%dT%H%M%SZ") if event.created_at else datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
        f'LAST-MODIFIED:{event.updated_at.strftime("%Y%m%dT%H%M%SZ") if event.updated_at else datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
        'STATUS:CONFIRMED',
        'TRANSP:OPAQUE',
        'END:VEVENT',
        'END:VCALENDAR'
    ]
    
    return '\r\n'.join(ics_lines) + '\r\n'

def generate_ics_calendar(events, include_weekly_holidays=False):
    """Generate ICS content for multiple events"""
    ics_lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Khulna University//Academic Calendar//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:Academic Calendar - Khulna University',
        'X-WR-CALDESC:Academic Calendar Events and Holidays',
        'X-WR-TIMEZONE:Asia/Dhaka'
    ]
    
    # Add weekly holidays if requested
    if include_weekly_holidays:
        # Get date range from events or use current year
        if events:
            start_year = min(e.event_date.year for e in events)
            end_year = max((e.end_date or e.event_date).year for e in events)
        else:
            start_year = datetime.now().year
            end_year = datetime.now().year
        
        current_date = date(start_year, 1, 1)
        end_date = date(end_year, 12, 31)
        
        while current_date <= end_date:
            if current_date.weekday() == 4:  # Friday
                dtstart = current_date.strftime('%Y%m%d')
                dtend = (current_date + timedelta(days=1)).strftime('%Y%m%d')
                uid = f"weekly-friday-{current_date.strftime('%Y%m%d')}@khulna-university"
                ics_lines.extend([
                    'BEGIN:VEVENT',
                    f'UID:{uid}',
                    f'DTSTART;VALUE=DATE:{dtstart}',
                    f'DTEND;VALUE=DATE:{dtend}',
                    'SUMMARY:শুক্রবার (ছুটি)',
                    'DESCRIPTION:Weekly Holiday - Friday',
                    f'DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
                    'STATUS:CONFIRMED',
                    'TRANSP:OPAQUE',
                    'RRULE:FREQ=WEEKLY;BYDAY=FR;INTERVAL=1',
                    'END:VEVENT'
                ])
            elif current_date.weekday() == 5:  # Saturday
                dtstart = current_date.strftime('%Y%m%d')
                dtend = (current_date + timedelta(days=1)).strftime('%Y%m%d')
                uid = f"weekly-saturday-{current_date.strftime('%Y%m%d')}@khulna-university"
                ics_lines.extend([
                    'BEGIN:VEVENT',
                    f'UID:{uid}',
                    f'DTSTART;VALUE=DATE:{dtstart}',
                    f'DTEND;VALUE=DATE:{dtend}',
                    'SUMMARY:শনিবার (ছুটি)',
                    'DESCRIPTION:Weekly Holiday - Saturday',
                    f'DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
                    'STATUS:CONFIRMED',
                    'TRANSP:OPAQUE',
                    'RRULE:FREQ=WEEKLY;BYDAY=SA;INTERVAL=1',
                    'END:VEVENT'
                ])
            current_date += timedelta(days=1)
            if current_date.year > end_year:
                break
    
    def escape_ics_text(text):
        if not text:
            return ''
        text = str(text).replace('\\', '\\\\')
        text = text.replace(',', '\\,')
        text = text.replace(';', '\\;')
        text = text.replace('\n', '\\n')
        return text

    # Merge semester start/end duplicates for ICS output.
    semester_groups = defaultdict(list)
    normalized_events = []
    for event in events:
        if getattr(event, 'event_type', None) in ('semester_start', 'semester_end'):
            semester_groups[(event.event_date, event.event_type)].append(event)
        else:
            normalized_events.append(event)

    for (event_day, event_type), grouped_events in semester_groups.items():
        if len(grouped_events) == 1:
            normalized_events.append(grouped_events[0])
            continue
        grouped_event = _build_semester_grouped_event(event_type, grouped_events, event_day)
        if grouped_event:
            normalized_events.append(grouped_event)

    normalized_events.sort(
        key=lambda e: e['event_date'] if isinstance(e, dict) else e.event_date
    )

    # Add regular and grouped events
    for event in normalized_events:
        if isinstance(event, dict):
            event_date = event.get('event_date')
            end_date = event.get('end_date')
            title_raw = event.get('title')
            description_raw = event.get('description')
            uid = f"{event.get('id', 'academic-event')}-ics@khulna-university"
            created_at = event.get('created_at')
            updated_at = event.get('updated_at')
        else:
            event_date = event.event_date
            end_date = event.end_date
            title_raw = event.title
            description_raw = event.description or ''
            uid = f"academic-event-{event.id}@khulna-university"
            created_at = event.created_at
            updated_at = event.updated_at

        dtstart = event_date.strftime('%Y%m%d')
        if end_date and end_date > event_date:
            end_date_calc = end_date + timedelta(days=1)
            dtend = end_date_calc.strftime('%Y%m%d')
        else:
            end_date_calc = event_date + timedelta(days=1)
            dtend = end_date_calc.strftime('%Y%m%d')

        title = escape_ics_text(title_raw)
        description = escape_ics_text(description_raw or '')

        ics_lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTART;VALUE=DATE:{dtstart}',
            f'DTEND;VALUE=DATE:{dtend}',
            f'SUMMARY:{title}',
            f'DESCRIPTION:{description}',
            f'DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
            f'CREATED:{created_at.strftime("%Y%m%dT%H%M%SZ") if created_at else datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
            f'LAST-MODIFIED:{updated_at.strftime("%Y%m%dT%H%M%SZ") if updated_at else datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}',
            'STATUS:CONFIRMED',
            'TRANSP:OPAQUE',
            'END:VEVENT'
        ])
    
    ics_lines.append('END:VCALENDAR')
    
    return '\r\n'.join(ics_lines) + '\r\n'


# ============================================================================
# Batch Custom Events Routes (Teacher-specific events for specific batches)
# ============================================================================

@academic_calendar_bp.route('/batch-events')
@login_required
def batch_events_index():
    """Display assessment schedules - teachers see their events, students see their batch events"""
    if not current_user.is_authenticated:
        flash('Please login to view assessment schedules.', 'warning')
        return redirect(url_for('auth.login'))
    
    roles = set(parse_roles(current_user.role))
    is_teacher = has_teacher_privileges(current_user)
    is_student = 'student' in roles
    
    if is_teacher:
        # Teachers see all events they created for their sessions
        teacher = Teacher.query.filter_by(name=current_user.full_name).first()
        if not teacher:
            flash('Teacher profile not found.', 'warning')
            return redirect(url_for('academic_calendar.index'))
        
        # Get all sessions for this teacher
        sessions = query_for_window(Session).filter_by(teacher_id=teacher.id, archived=False).all()
        session_ids = [s.id for s in sessions]
        
        # Get all batch events for these sessions
        events = _batch_events_query().filter(
            BatchCustomEvent.session_id.in_(session_ids)
        ).order_by(BatchCustomEvent.event_date.desc(), BatchCustomEvent.event_time.asc()).all()
        
        # Group events by session
        events_by_session = {}
        for event in events:
            if event.session_id not in events_by_session:
                events_by_session[event.session_id] = []
            events_by_session[event.session_id].append(event)
        
        return render_template('academic_calendar/batch_events_teacher.html',
                             events=events,
                             events_by_session=events_by_session,
                             sessions=sessions)
    
    elif is_student:
        # Students see only events for their batch
        student = Student.query.filter_by(student_id=current_user.username).first()
        if not student or not student.batch:
            flash('Student batch information not found. Please contact administrator.', 'warning')
            return redirect(url_for('academic_calendar.index'))
        
        # Get all events for this batch
        events = _batch_events_query().filter_by(batch=student.batch).order_by(
            BatchCustomEvent.event_date.asc(),
            BatchCustomEvent.event_time.asc()
        ).all()
        
        # Get upcoming events (today or later)
        today = date.today()
        upcoming_events = [e for e in events if e.event_date >= today]
        past_events = [e for e in events if e.event_date < today]
        
        return render_template('academic_calendar/batch_events_student.html',
                             events=events,
                             upcoming_events=upcoming_events,
                             past_events=past_events,
                             student_batch=student.batch)
    else:
        flash('You do not have permission to view assessment schedules.', 'danger')
        return redirect(url_for('academic_calendar.index'))


@academic_calendar_bp.route('/batch-events/add', methods=['GET', 'POST'])
@login_required
def add_batch_event():
    """Add a new batch-specific custom event (Teachers only)"""
    if not has_teacher_privileges(current_user):
        flash('Only teachers can create assessment schedules.', 'danger')
        return redirect(url_for('academic_calendar.batch_events_index'))
    
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        flash('Teacher profile not found. Please ensure your name matches the teacher record.', 'warning')
        current_app.logger.warning(f"Teacher not found for user: {current_user.full_name}")
        return redirect(url_for('academic_calendar.batch_events_index'))
    
    # Get teacher's active sessions
    sessions = query_for_window(Session).filter_by(teacher_id=teacher.id, archived=False).order_by(
        Session.created_at.desc()
    ).all()
    
    if not sessions:
        flash('No active courses found. Please create a class session first.', 'warning')
        return redirect(url_for('class_management.index'))
    
    if request.method == 'POST':
        try:
            current_app.logger.info(f"Processing batch event creation request from user: {current_user.full_name}")
            
            session_id = request.form.get('session_id', type=int)
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            event_date_str = request.form.get('event_date', '').strip()
            event_time_str = request.form.get('event_time', '').strip()
            event_type = 'custom'  # Default event type, no longer needed from form
            location = request.form.get('location', '').strip()
            
            current_app.logger.debug(f"Form data: session_id={session_id}, title={title}, date={event_date_str}")
            
            # Validation
            if not session_id or not title or not event_date_str:
                missing = []
                if not session_id: missing.append('Course')
                if not title: missing.append('Title')
                if not event_date_str: missing.append('Date')
                flash(f'Missing required fields: {", ".join(missing)}. Please fill in all required fields.', 'error')
                current_app.logger.warning(f"Validation failed: missing {missing}")
                return redirect(url_for('academic_calendar.add_batch_event'))
            
            # Verify session belongs to teacher
            session = query_for_window(Session).filter_by(id=session_id, teacher_id=teacher.id).first()
            if not session:
                flash('Invalid session selected.', 'error')
                return redirect(url_for('academic_calendar.add_batch_event'))
            
            # Parse date
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format.', 'error')
                return redirect(url_for('academic_calendar.add_batch_event'))
            
            # Parse time (optional)
            event_time = None
            if event_time_str:
                try:
                    event_time = datetime.strptime(event_time_str, '%H:%M').time()
                except ValueError:
                    flash('Invalid time format. Use HH:MM format.', 'error')
                    return redirect(url_for('academic_calendar.add_batch_event'))
            
            # Get all batches from students enrolled in this session
            class_students = ClassStudent.query.filter_by(session_id=session_id).all()
            batch_set = set()
            for cs in class_students:
                student = Student.query.filter_by(student_id=cs.student_id).first()
                if student and student.batch:
                    batch_set.add(student.batch)
            
            if not batch_set:
                flash('No students found in this course. Please add students to the course first.', 'warning')
                return redirect(url_for('academic_calendar.add_batch_event'))
            
            batches = sorted(list(batch_set), reverse=True)
            current_app.logger.info(f"Creating batch events for session {session_id}: {title} for batches {batches}")
            
            # Create event for each batch in the session
            get_or_404_for_window(Session, session_id)
            events_created = []
            for batch in batches:
                event = BatchCustomEvent(
                    session_id=session_id,
                    batch=batch,
                    title=title,
                    description=description or None,
                    event_date=event_date,
                    event_time=event_time,
                    event_type=event_type,
                    location=location or None,
                    created_by_id=current_user.id
                )
                db.session.add(event)
                events_created.append(batch)
            
            try:
                db.session.commit()
                batch_list = ', '.join([f'Batch {b}' for b in batches])
                current_app.logger.info(f"✓ Batch events added successfully: {title} for {batch_list} by teacher {current_user.full_name}")
                if len(batches) == 1:
                    flash(f'Assessment schedule "{title}" added successfully for {batch_list}.', 'success')
                else:
                    flash(f'Assessment schedule "{title}" added successfully for {len(batches)} batches ({batch_list}).', 'success')
                return redirect(url_for('academic_calendar.batch_events_index'))
            except Exception as commit_error:
                db.session.rollback()
                current_app.logger.error(f"Database commit error: {commit_error}", exc_info=True)
                raise
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding batch event: {e}", exc_info=True)
            error_msg = str(e)
            # Check for common database errors
            if 'no such table' in error_msg.lower() or 'does not exist' in error_msg.lower():
                flash('Database table not found. Please run: python3 create_batch_custom_event_table.py', 'error')
            elif 'no such column' in error_msg.lower():
                flash('Database schema issue. Please run: python3 create_batch_custom_event_table.py', 'error')
            else:
                flash(f'Error adding event: {error_msg[:150]}. Please check all fields and try again.', 'error')
            return redirect(url_for('academic_calendar.add_batch_event'))
    
    # Check if session_id is passed as query parameter (from assessment schedule page)
    preselected_session_id = request.args.get('session_id', type=int)
    
    current_app.logger.info(f"Rendering add_batch_event form: {len(sessions)} sessions")
    
    return render_template('academic_calendar/add_batch_event.html',
                         sessions=sessions,
                         preselected_session_id=preselected_session_id)


@academic_calendar_bp.route('/batch-events/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_batch_event(event_id):
    """Edit a batch-specific custom event (Teachers only)"""
    if not has_teacher_privileges(current_user):
        flash('Only teachers can edit assessment schedules.', 'danger')
        return redirect(url_for('academic_calendar.batch_events_index'))
    
    event = _get_batch_event_or_404(event_id)
    
    # Verify teacher owns this event's session
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher or event.session.teacher_id != teacher.id:
        flash('You do not have permission to edit this event.', 'danger')
        return redirect(url_for('academic_calendar.batch_events_index'))
    
    if request.method == 'POST':
        try:
            batch = request.form.get('batch', '').strip()
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            event_date_str = request.form.get('event_date', '').strip()
            event_time_str = request.form.get('event_time', '').strip()
            event_type = request.form.get('event_type', 'custom').strip()
            location = request.form.get('location', '').strip()
            
            # Validation
            if not batch or not title or not event_date_str:
                flash('Batch, Title, and Date are required.', 'error')
                return redirect(url_for('academic_calendar.edit_batch_event', event_id=event_id))
            
            # Parse date
            try:
                event.event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format.', 'error')
                return redirect(url_for('academic_calendar.edit_batch_event', event_id=event_id))
            
            # Parse time (optional)
            if event_time_str:
                try:
                    event.event_time = datetime.strptime(event_time_str, '%H:%M').time()
                except ValueError:
                    flash('Invalid time format. Use HH:MM format.', 'error')
                    return redirect(url_for('academic_calendar.edit_batch_event', event_id=event_id))
            else:
                event.event_time = None
            
            # Update fields
            event.batch = batch
            event.title = title
            event.description = description or None
            event.event_type = event_type
            event.location = location or None
            
            db.session.commit()
            
            current_app.logger.info(f"Batch event updated: {title} for batch {batch}")
            flash(f'Assessment schedule "{title}" updated successfully.', 'success')
            return redirect(url_for('academic_calendar.batch_events_index'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating batch event: {e}", exc_info=True)
            flash(f'Error updating event: {str(e)[:100]}. Please try again.', 'error')
            return redirect(url_for('academic_calendar.edit_batch_event', event_id=event_id))
    
    return render_template('academic_calendar/edit_batch_event.html', event=event)


@academic_calendar_bp.route('/assessment-schedule/<int:session_id>')
@login_required
def assessment_schedule(session_id):
    """Display assessment schedule for a specific course/session"""
    try:
        session = get_or_404_for_window(Session, session_id)
        
        # Check if user has access to this session
        if has_teacher_privileges(current_user):
            teacher = Teacher.query.filter_by(name=current_user.full_name).first()
            if teacher and session.teacher_id != teacher.id:
                flash('You do not have permission to view this course assessment schedule.', 'danger')
                return redirect(url_for('class_management.index'))
        elif 'student' in parse_roles(current_user.role):
            # Students can view their own course schedules
            student = Student.query.filter_by(student_id=current_user.username).first()
            if not student:
                flash('Student profile not found.', 'warning')
                return redirect(url_for('academic_calendar.index'))
            
            # Check if student is enrolled in this session
            class_student = ClassStudent.query.filter_by(
                session_id=session_id,
                student_id=student.student_id
            ).first()
            
            if not class_student:
                flash('You are not enrolled in this course.', 'warning')
                return redirect(url_for('academic_calendar.index'))
        else:
            flash('You do not have permission to view assessment schedules.', 'danger')
            return redirect(url_for('academic_calendar.index'))
        
        # Get batch events for this session (these are the assessment schedules)
        batch_events = _batch_events_query().filter_by(session_id=session_id).order_by(
            BatchCustomEvent.event_date.asc(),
            BatchCustomEvent.event_time.asc()
        ).all()
        
        # Group events by date
        events_by_date = {}
        for event in batch_events:
            date_str = event.event_date.strftime('%Y-%m-%d')
            if date_str not in events_by_date:
                events_by_date[date_str] = []
            events_by_date[date_str].append(event)
        
        # Get upcoming and past events
        today = date.today()
        upcoming_events = [e for e in batch_events if e.event_date >= today]
        past_events = [e for e in batch_events if e.event_date < today]
        
        return render_template('academic_calendar/assessment_schedule.html',
                             session=session,
                             events_by_date=events_by_date,
                             upcoming_events=upcoming_events,
                             past_events=past_events,
                             today=today,
                             parse_roles=parse_roles,
                             has_teacher_privileges=has_teacher_privileges,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error displaying assessment schedule: {e}", exc_info=True)
        flash('Error loading assessment schedule.', 'error')
        return redirect(url_for('class_management.index'))


@academic_calendar_bp.route('/batch-events/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_batch_event(event_id):
    """Delete a batch-specific custom event (Teachers only)"""
    if not has_teacher_privileges(current_user):
        return jsonify({'success': False, 'message': 'Only teachers can delete assessment schedules.'}), 403
    
    try:
        event = _get_batch_event_or_404(event_id)
        
        # Verify teacher owns this event's session
        teacher = Teacher.query.filter_by(name=current_user.full_name).first()
        if not teacher or event.session.teacher_id != teacher.id:
            return jsonify({'success': False, 'message': 'You do not have permission to delete this event.'}), 403
        
        event_title = event.title
        db.session.delete(event)
        db.session.commit()
        
        current_app.logger.info(f"Batch event deleted: {event_title}")
        return jsonify({'success': True, 'message': 'Event deleted successfully.'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting batch event: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error deleting event.'}), 500
