"""Academic calendar helpers for AI outline generation."""
import re
from datetime import date, timedelta


def _normalize_year_term(value, is_term=False):
    if not value:
        return ''
    value = str(value).strip().lower()
    value = value.replace(' year', '').replace(' term', '').strip()
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


def _normalize_academic_session(value):
    text = (value or '').strip().lower().replace(' ', '')
    text = text.replace('–', '-').replace('—', '-')
    match = re.match(r'(20\d{2})-20(\d{2})$', text)
    if match:
        return f'{match.group(1)}-{match.group(2)}'
    return text


def calendar_query_range(academic_session=None):
    """Wide date window so 2024-25 events still load in 2026."""
    years = {date.today().year}
    for token in re.findall(r'(?:19|20)\d{2}', academic_session or ''):
        year = int(token)
        years.add(year)
        years.add(year + 1)
    low = min(years) - 1
    high = max(years) + 1
    return date(max(low, 2000), 1, 1), date(high, 12, 31)


def years_in_academic_session(academic_session=None):
    years = set()
    for token in re.findall(r'(?:19|20)\d{2}', academic_session or ''):
        year = int(token)
        years.add(year)
        years.add(year + 1)
    return years


def semester_event_context(event):
    """Year / Term / Academic Session stored in calendar event title or description."""
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


def _event_match_score(event, academic_session, year, term):
    ctx = semester_event_context(event)
    want_year = _normalize_year_term(year, is_term=False)
    want_term = _normalize_year_term(term, is_term=True)
    want_session = _normalize_academic_session(academic_session)
    got_year = _normalize_year_term(ctx.get('year'), is_term=False)
    got_term = _normalize_year_term(ctx.get('term'), is_term=True)
    got_session = _normalize_academic_session(ctx.get('session'))
    blob = f'{(event.title or "")} {(event.description or "")}'.lower().replace(' ', '')

    score = 0
    if want_session and (got_session == want_session or want_session in blob):
        score += 4
    if want_year and (got_year == want_year or want_year in blob):
        score += 2
    if want_term and (got_term == want_term or want_term in blob):
        score += 2
    return score


def _match_semester_event(events, academic_session, year, term):
    if not events:
        return None
    ranked = sorted(
        events,
        key=lambda event: (-_event_match_score(event, academic_session, year, term), event.event_date or date.min),
    )
    best = ranked[0]
    if _event_match_score(best, academic_session, year, term) >= 2:
        return best
    return None


def _fallback_semester_event(events, academic_session, after_date=None):
    if not events:
        return None
    pool = list(events)
    if after_date:
        later = [e for e in pool if e.event_date and e.event_date > after_date]
        if later:
            pool = later
    session_years = years_in_academic_session(academic_session)
    if session_years:
        in_years = [e for e in pool if e.event_date and e.event_date.year in session_years]
        if in_years:
            pool = in_years
    if after_date:
        return min(pool, key=lambda e: e.event_date)
    today = date.today()
    upcoming = [e for e in pool if e.event_date and e.event_date >= today]
    if upcoming:
        return min(upcoming, key=lambda e: e.event_date)
    return max(pool, key=lambda e: e.event_date)


def resolve_semester_dates(calendar_events, academic_session='', year='', term=''):
    """Find semester start/end from AcademicCalendarEvent rows."""
    start_events = [e for e in calendar_events or [] if getattr(e, 'event_type', None) == 'semester_start']
    end_events = [e for e in calendar_events or [] if getattr(e, 'event_type', None) == 'semester_end']

    matched_start = _match_semester_event(start_events, academic_session, year, term)
    if not matched_start:
        matched_start = _fallback_semester_event(start_events, academic_session)

    semester_start = matched_start.event_date if matched_start else None

    matched_end = _match_semester_event(end_events, academic_session, year, term)
    if not matched_end:
        matched_end = _fallback_semester_event(end_events, academic_session, after_date=semester_start)

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
    """Human-readable calendar context for AI prompts and local lesson plans."""
    semester_start, semester_end = resolve_semester_dates(
        calendar_events, academic_session=academic_session, year=year, term=term
    )
    holiday_start = semester_start or date(date.today().year, 1, 1)
    holiday_end = semester_end or date(date.today().year + 1, 12, 31)
    holidays = collect_holidays(calendar_events, holiday_start, holiday_end)
    working_days = count_working_days(semester_start, semester_end, holidays) if semester_start and semester_end else 0

    holiday_labels = []
    for event in calendar_events or []:
        if getattr(event, 'event_type', None) != 'holiday':
            continue
        event_date = getattr(event, 'event_date', None)
        if semester_start and event_date and event_date < semester_start:
            continue
        if semester_end and event_date and event_date > semester_end:
            continue
        holiday_labels.append(f'{getattr(event, "title", "Holiday")} ({event_date})')
    holiday_labels = sorted(set(holiday_labels))

    working_dates = []
    if semester_start and semester_end:
        current = semester_start
        while current <= semester_end:
            if current.weekday() not in (4, 5) and current not in holidays:
                working_dates.append(current.isoformat())
            current += timedelta(days=1)

    in_semester_holidays = 0
    if semester_start and semester_end:
        in_semester_holidays = len([
            d for d in holidays
            if semester_start <= d <= semester_end and d.weekday() not in (4, 5)
        ])

    return {
        'semester_start': semester_start.isoformat() if semester_start else None,
        'semester_end': semester_end.isoformat() if semester_end else None,
        'working_days': working_days,
        'holiday_count': in_semester_holidays,
        'holidays': holiday_labels[:40],
        'working_dates': working_dates,
        'weekend_rule': 'Friday and Saturday are non-working days',
    }


def _as_date(value):
    if isinstance(value, date):
        return value
    text = str(value or '').strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def sunday_of_week(day):
    """Bangladesh academic week starts on Sunday."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def group_working_dates_into_weeks(iso_dates):
    """Group Sun–Thu working days into Bangladesh academic weeks."""
    days = []
    for raw in iso_dates or []:
        parsed = _as_date(raw)
        if parsed:
            days.append(parsed)
    days.sort()

    weeks = []
    current = []
    current_week_start = None
    for day in days:
        week_start = sunday_of_week(day)
        if current_week_start is None:
            current_week_start = week_start
            current = [day]
        elif week_start != current_week_start:
            weeks.append(current)
            current_week_start = week_start
            current = [day]
        else:
            current.append(day)
    if current:
        weeks.append(current)
    return weeks


def format_week_date_range(days):
    """Date field value: '20-24 July 2025' or '28 Jul 2025 to 1 Aug 2025'."""
    if not days:
        return ''
    start, end = days[0], days[-1]
    if start == end:
        return f"{start.day} {start.strftime('%B')} {start.year}"
    if start.month == end.month and start.year == end.year:
        return f"{start.day}-{end.day} {end.strftime('%B')} {end.year}"
    return (
        f"{start.day} {start.strftime('%b')} {start.year} "
        f"to {end.day} {end.strftime('%b')} {end.year}"
    )
