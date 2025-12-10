from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, Response
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import or_, and_
from extensions import db
from .models import AcademicCalendarEvent
from user_models import User
from role_utils import parse_roles
from . import academic_calendar_bp

def can_edit_calendar():
    """Check if current user can edit calendar (Head or Teaching Assistant)"""
    if not current_user.is_authenticated:
        return False
    roles = set(parse_roles(current_user.role))
    if getattr(current_user, 'active_role', None):
        roles = set(parse_roles(current_user.active_role))
    return 'head' in roles or 'teaching_assistant' in roles

@academic_calendar_bp.route('/')
@login_required
def index():
    """Display academic calendar with events and holidays"""
    try:
        # Ensure table exists - try to create if it doesn't
        try:
            # Quick check if table exists by trying a simple query
            AcademicCalendarEvent.query.limit(1).all()
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
                                         view_type='month')
        
        # Get view type (year or month), default to month
        view_type = request.args.get('view', 'month')
        
        # Get current year and month from request or use current date
        year = request.args.get('year', type=int) or datetime.now().year
        month = request.args.get('month', type=int) or datetime.now().month
        
        # Get all events for the year
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        try:
            events = AcademicCalendarEvent.query.filter(
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
                    events = AcademicCalendarEvent.query.filter(
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
        
        can_edit = can_edit_calendar()
        
        # Prepare upcoming events list (sorted by date)
        upcoming_events_list = []
        today = date.today()
        for event in events:
            if event.event_date >= today:
                upcoming_events_list.append((event.event_date, event))
        upcoming_events_list.sort(key=lambda x: x[0])
        
        return render_template(
            'academic_calendar/index.html',
            year=year,
            month=month,
            events_by_date=events_by_date,
            can_edit=can_edit,
            current_date=today,
            upcoming_events=upcoming_events_list[:10],
            view_type=view_type
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
                                     view_type='month')
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
                                 view_type='month')

@academic_calendar_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_event():
    """Add a new calendar event"""
    if not can_edit_calendar():
        flash('You do not have permission to edit the calendar.', 'danger')
        return redirect(url_for('academic_calendar.index'))
    
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
            
            event = AcademicCalendarEvent(
                title=title,
                description=description or None,
                event_date=event_date,
                end_date=end_date,
                event_type=event_type,
                created_by_id=current_user.id
            )
            
            db.session.add(event)
            try:
                db.session.commit()
                current_app.logger.info(f"Event added successfully: {event.title} on {event.event_date}")
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
    
    return render_template('academic_calendar/add_event.html')

@academic_calendar_bp.route('/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """Edit an existing calendar event"""
    if not can_edit_calendar():
        flash('You do not have permission to edit the calendar.', 'danger')
        return redirect(url_for('academic_calendar.index'))
    
    event = AcademicCalendarEvent.query.get_or_404(event_id)
    
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
        event = AcademicCalendarEvent.query.get_or_404(event_id)
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
        
        events = AcademicCalendarEvent.query.filter(
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
        event = AcademicCalendarEvent.query.get_or_404(event_id)
        
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
        events = AcademicCalendarEvent.query.order_by(AcademicCalendarEvent.event_date.asc()).all()
        
        # Generate ICS content for all events
        ics_content = generate_ics_calendar(events, include_weekly_holidays=True)
        
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
    
    # Add regular events
    for event in events:
        dtstart = event.event_date.strftime('%Y%m%d')
        dtend = event.end_date.strftime('%Y%m%d') if event.end_date else event.event_date.strftime('%Y%m%d')
        
        if event.end_date and event.end_date > event.event_date:
            end_date_calc = event.end_date + timedelta(days=1)
            dtend = end_date_calc.strftime('%Y%m%d')
        else:
            end_date_calc = event.event_date + timedelta(days=1)
            dtend = end_date_calc.strftime('%Y%m%d')
        
        uid = f"academic-event-{event.id}@khulna-university"
        
        def escape_ics_text(text):
            if not text:
                return ''
            text = str(text).replace('\\', '\\\\')
            text = text.replace(',', '\\,')
            text = text.replace(';', '\\;')
            text = text.replace('\n', '\\n')
            return text
        
        title = escape_ics_text(event.title)
        description = escape_ics_text(event.description or '')
        
        ics_lines.extend([
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
            'END:VEVENT'
        ])
    
    ics_lines.append('END:VCALENDAR')
    
    return '\r\n'.join(ics_lines) + '\r\n'
