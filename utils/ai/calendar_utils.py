"""Academic calendar helpers for AI outline generation."""
from datetime import date, timedelta


def _normalize_year_term(value, is_term=False):
    if not value:
        return ''
    value = str(value).strip().lower()
    if is_term:
        term_map = {'1': 'first', '1st': 'first', 'first': 'first', '2': 'second', '2nd': 'second', 'second': 'second'}
        return term_map.get(value, value)
    year_map = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second',
        '3': 'third', '3rd': 'third', 'third': 'third',
        '4': 'fourth', '4th': 'fourth', 'fourth': 'fourth',
        '5': 'fifth', '5th': 'fifth', 'fifth': 'fifth', 'llm': 'fifth',
    }
    return year_map.get(value, value)


def collect_holidays(calendar_events, year_start=None, year_end=None):
    """Return set of holiday dates including Fri/Sat weekends."""
    if year_start is None:
        year_start = date(date.today().year, 1, 1)
    if year_end is None:
        year_end = date(date.today().year + 1, 12, 31)

    holidays = set()
    for event in calendar_events or []:
        if getattr(event, 'event_type', None) != 'holiday':
            continue
        end_date = getattr(event, 'end_date', None)
        event_date = getattr(event, 'event_date', None)
        if not event_date:
            continue
        if end_date and end_date > event_date:
            current = event_date
            while current <= end_date:
                holidays.add(current)
                current += timedelta(days=1)
        else:
            holidays.add(event_date)

    current = year_start
    while current <= year_end:
        if current.weekday() in (4, 5):
            holidays.add(current)
        current += timedelta(days=1)
    return holidays


def _match_semester_event(events, academic_session, normalized_year, normalized_term):
    if not events:
        return None
    if academic_session:
        for event in events:
            text = f'{(event.title or "").lower()} {(event.description or "").lower()}'
            if (
                academic_session.lower() in text
                and normalized_year in text
                and normalized_term in text
            ):
                return event
    for event in events:
        text = f'{(event.title or "").lower()} {(event.description or "").lower()}'
        if normalized_year in text and normalized_term in text:
            return event
    return None


def resolve_semester_dates(calendar_events, academic_session='', year='', term=''):
    """Find semester start/end from AcademicCalendarEvent rows."""
    normalized_year = _normalize_year_term(year, is_term=False)
    normalized_term = _normalize_year_term(term, is_term=True)
    start_events = [e for e in calendar_events or [] if getattr(e, 'event_type', None) == 'semester_start']
    end_events = [e for e in calendar_events or [] if getattr(e, 'event_type', None) == 'semester_end']

    matched_start = _match_semester_event(start_events, academic_session, normalized_year, normalized_term)
    if not matched_start and start_events:
        today = date.today()
        upcoming = [e for e in start_events if e.event_date >= today]
        matched_start = min(upcoming, key=lambda x: x.event_date) if upcoming else max(start_events, key=lambda x: x.event_date)

    semester_start = matched_start.event_date if matched_start else None

    matched_end = _match_semester_event(end_events, academic_session, normalized_year, normalized_term)
    if not matched_end and end_events:
        if semester_start:
            future = [e for e in end_events if e.event_date > semester_start]
            if future:
                matched_end = min(future, key=lambda x: x.event_date)
        if not matched_end:
            today = date.today()
            upcoming = [e for e in end_events if e.event_date >= today]
            matched_end = min(upcoming, key=lambda x: x.event_date) if upcoming else max(end_events, key=lambda x: x.event_date)

    semester_end = matched_end.event_date if matched_end else None
    return semester_start, semester_end


def count_working_days(start_date, end_date, holidays):
    if not start_date or not end_date or end_date <= start_date:
        return 0
    count = 0
    current = start_date
    while current <= end_date:
        if current.weekday() not in (4, 5) and current not in holidays:
            count += 1
        current += timedelta(days=1)
    return count


def build_calendar_summary(calendar_events, academic_session='', year='', term=''):
    """Human-readable calendar context for AI prompts."""
    year_start = date(date.today().year, 1, 1)
    year_end = date(date.today().year + 1, 12, 31)
    holidays = collect_holidays(calendar_events, year_start, year_end)
    semester_start, semester_end = resolve_semester_dates(
        calendar_events, academic_session=academic_session, year=year, term=term
    )
    working_days = count_working_days(semester_start, semester_end, holidays) if semester_start and semester_end else 0

    holiday_labels = sorted({
        f'{getattr(e, "title", "Holiday")} ({getattr(e, "event_date", "")})'
        for e in (calendar_events or [])
        if getattr(e, 'event_type', None) == 'holiday'
    })

    return {
        'semester_start': semester_start.isoformat() if semester_start else None,
        'semester_end': semester_end.isoformat() if semester_end else None,
        'working_days': working_days,
        'holiday_count': len(holidays),
        'holidays': holiday_labels[:30],
        'weekend_rule': 'Friday and Saturday are non-working days',
    }
