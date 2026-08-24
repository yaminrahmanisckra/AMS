"""Rule-based conflict-free routine placer. Does not invent slots via LLM."""
import re


def _norm(value):
    return str(value or '').strip()


def _int_or_none(value):
    try:
        if value in (None, ''):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _semester_key(year, term, batch):
    return '|'.join([
        _norm(year).lower(),
        _norm(term).lower(),
        _norm(batch).lower(),
    ])


def _classes_needed(course):
    try:
        needed = int(course.get('classes_per_week') or 0)
    except (TypeError, ValueError):
        needed = 0
    return max(0, needed)


_DAY_ALIASES = {
    'sunday': 'Sunday', 'sun': 'Sunday', 'রবিবার': 'Sunday', 'রবি': 'Sunday',
    'monday': 'Monday', 'mon': 'Monday', 'সোমবার': 'Monday', 'সোম': 'Monday',
    'tuesday': 'Tuesday', 'tue': 'Tuesday', 'মঙ্গলবার': 'Tuesday', 'মঙ্গল': 'Tuesday',
    'wednesday': 'Wednesday', 'wed': 'Wednesday', 'বুধবার': 'Wednesday', 'বুধ': 'Wednesday',
    'thursday': 'Thursday', 'thu': 'Thursday', 'বৃহস্পতিবার': 'Thursday', 'বৃহস্পতি': 'Thursday',
    'friday': 'Friday', 'fri': 'Friday', 'শুক্রবার': 'Friday', 'শুক্র': 'Friday',
    'saturday': 'Saturday', 'sat': 'Saturday', 'শনিবার': 'Saturday', 'শনি': 'Saturday',
}


def _match_days(text):
    found = []
    lowered = (text or '').lower()
    for alias, day in _DAY_ALIASES.items():
        if alias.lower() in lowered and day not in found:
            found.append(day)
    return found


def parse_preferences(prompt=None, preferences=None):
    """Merge UI preferences with free-text prompt into solver constraints."""
    prefs = dict(preferences or {})
    text = _norm(prompt or prefs.get('prompt') or '')
    prefer_days = list(prefs.get('prefer_days') or [])
    avoid_days = list(prefs.get('avoid_days') or [])
    time_of_day = prefs.get('time_of_day')  # morning | afternoon | None
    same_room = bool(prefs.get('same_room'))
    avoid_consecutive = bool(prefs.get('avoid_consecutive'))
    prefer_spread = prefs.get('prefer_spread', True)

    if text:
        lowered = text.lower()
        # Per-day local context: "...রবিবারে দিও না" vs "শুধু সোমবার"
        for alias, day in _DAY_ALIASES.items():
            for match in re.finditer(re.escape(alias.lower()), lowered):
                start = max(0, match.start() - 18)
                end = min(len(lowered), match.end() + 18)
                window = lowered[start:end]
                is_avoid = bool(re.search(
                    r'(avoid|বাদ|দিও\s*না|দিবে\s*না|দেবে\s*না|দিয়ো\s*না|ছাড়া|এড়ি|না\s*দি)',
                    window,
                ))
                is_only = bool(re.search(r'(শুধু|কেবল|only|prefer|পছন্দ)', window))
                if is_avoid:
                    if day not in avoid_days:
                        avoid_days.append(day)
                    if day in prefer_days:
                        prefer_days = [d for d in prefer_days if d != day]
                elif is_only:
                    if day not in prefer_days and day not in avoid_days:
                        prefer_days.append(day)

        if re.search(r'(সকাল|morning|before\s*lunch|লাঞ্চের?\s*আগে|প্রথম\s*ভাগ)', text, re.I):
            time_of_day = time_of_day or 'morning'
        if re.search(r'(বিকাল|afternoon|after\s*lunch|লাঞ্চের?\s*পরে|শেষ\s*ভাগ)', text, re.I):
            time_of_day = time_of_day or 'afternoon'
        if re.search(r'(একই\s*রুম|same\s*room|এক\s*রুম)', text, re.I):
            same_room = True
        if re.search(r'(পরপর\s*না|consecutive|একটানা\s*না|পাশাপাশি\s*না)', text, re.I):
            avoid_consecutive = True
        if re.search(r'(আলাদা\s*দিন|spread|বিক্ষিপ্ত|ছড়ি)', text, re.I):
            prefer_spread = True

    # Prefer wins only if not also avoided
    prefer_days = [d for d in prefer_days if d not in avoid_days]

    return {
        'prefer_days': prefer_days,
        'avoid_days': avoid_days,
        'time_of_day': time_of_day,
        'same_room': same_room,
        'avoid_consecutive': avoid_consecutive,
        'prefer_spread': prefer_spread,
        'prompt': text,
    }


def explain_unplaced(unplaced):
    """Optional LLM-free explanations for leftover courses."""
    lines = []
    for row in unplaced:
        code = row.get('course_code') or 'Course'
        remaining = row.get('remaining') or 0
        reason = row.get('reason') or 'কোনো খালি কনফ্লিক্টহীন স্লট পাওয়া যায়নি।'
        lines.append(f"{code}: {remaining} class(es) unplaced — {reason}")
    return lines


def _slot_bucket(slot, time_slots):
    """morning = first half of day slots, afternoon = rest (after typical lunch)."""
    try:
        idx = time_slots.index(slot)
    except ValueError:
        return 'any'
    mid = max(1, len(time_slots) // 2)
    return 'morning' if idx < mid else 'afternoon'


def auto_place(
    days,
    time_slots,
    rooms,
    courses,
    existing=None,
    keep_existing=True,
    preferences=None,
    prompt=None,
    clear_course_ids=None,
):
    """
    Greedy placer with optional constraints.

    preferences/prompt may restrict days, morning/afternoon, same-room, etc.
    clear_course_ids: drop existing entries for these assigned_ids before placing.
    """
    days = [_norm(d) for d in (days or []) if _norm(d)]
    time_slots = [_norm(s) for s in (time_slots or []) if _norm(s)]
    rooms = list(rooms or [])
    prefs = parse_preferences(prompt, preferences)
    clear_ids = {_norm(x) for x in (clear_course_ids or []) if _norm(x)}

    existing = list(existing or [])
    if clear_ids:
        existing = [
            e for e in existing
            if _norm(e.get('assigned_id') or e.get('course_code')) not in clear_ids
        ]
    if not keep_existing:
        existing = []

    occupied_room = set()
    occupied_teacher = set()
    occupied_semester = set()
    placed_count = {}
    result = []
    course_day_used = {}  # cid -> set of days already used (this run)
    course_room = {}      # cid -> preferred room_id when same_room
    course_last_slot = {}  # cid -> (day, slot_index)

    def occupy(entry):
        day = _norm(entry.get('day'))
        slot = _norm(entry.get('slot'))
        room_id = _int_or_none(entry.get('room_id'))
        teacher_id = _int_or_none(entry.get('teacher_id'))
        sem = _semester_key(entry.get('year'), entry.get('term'), entry.get('batch'))
        occupied_room.add((day, slot, room_id))
        if teacher_id:
            occupied_teacher.add((day, slot, teacher_id))
        if sem != '||':
            occupied_semester.add((day, slot, sem))

    for entry in existing:
        occupy(entry)
        result.append(dict(entry))
        cid = _norm(entry.get('assigned_id') or entry.get('course_code'))
        if cid:
            placed_count[cid] = placed_count.get(cid, 0) + 1
            course_day_used.setdefault(cid, set()).add(_norm(entry.get('day')))
            if prefs['same_room'] and entry.get('room_id') is not None:
                course_room.setdefault(cid, _int_or_none(entry.get('room_id')))

    def can_place(day, slot, room_id, teacher_id, sem):
        if day in prefs['avoid_days']:
            return False
        if prefs['prefer_days'] and day not in prefs['prefer_days']:
            return False
        if prefs['time_of_day']:
            if _slot_bucket(slot, time_slots) != prefs['time_of_day']:
                return False
        if (day, slot, room_id) in occupied_room:
            return False
        if teacher_id and (day, slot, teacher_id) in occupied_teacher:
            return False
        if sem != '||' and (day, slot, sem) in occupied_semester:
            return False
        return True

    def score_candidate(cid, day, slot, room_id):
        score = 0
        used_days = course_day_used.get(cid) or set()
        if prefs['prefer_spread'] and day not in used_days:
            score += 40
        if prefs['prefer_days'] and day in prefs['prefer_days']:
            score += 20
        if prefs['same_room'] and course_room.get(cid) == room_id:
            score += 30
        elif prefs['same_room'] and cid not in course_room:
            score += 5
        last = course_last_slot.get(cid)
        if last:
            last_day, last_idx = last
            try:
                cur_idx = time_slots.index(slot)
            except ValueError:
                cur_idx = -1
            if prefs['avoid_consecutive'] and last_day == day and abs(cur_idx - last_idx) == 1:
                score -= 50
            elif last_day == day:
                score -= 10
        return score

    room_cycle = list(rooms)
    unplaced = []

    for course in courses or []:
        code = _norm(course.get('course_code'))
        if not code:
            continue
        cid = _norm(course.get('assigned_id') or course.get('id') or code)
        needed = _classes_needed(course)
        already = placed_count.get(cid, 0)
        remaining = max(0, needed - already)
        if remaining <= 0:
            continue

        teacher_id = _int_or_none(course.get('teacher_id'))
        sem = _semester_key(course.get('year'), course.get('term'), course.get('batch'))
        placed_now = 0
        last_day = None

        for _ in range(remaining):
            candidates = []
            day_order = days
            if last_day and last_day in days and prefs['prefer_spread']:
                idx = days.index(last_day)
                day_order = days[idx + 1:] + days[: idx + 1]
            for day in day_order:
                for slot in time_slots:
                    for room in room_cycle:
                        room_id = _int_or_none(room.get('id'))
                        if room_id is None:
                            continue
                        if prefs['same_room'] and cid in course_room and course_room[cid] != room_id:
                            continue
                        if can_place(day, slot, room_id, teacher_id, sem):
                            candidates.append((
                                score_candidate(cid, day, slot, room_id),
                                day,
                                slot,
                                room,
                            ))
            if not candidates:
                # Relax same_room if stuck
                if prefs['same_room'] and cid in course_room:
                    for day in day_order:
                        for slot in time_slots:
                            for room in room_cycle:
                                room_id = _int_or_none(room.get('id'))
                                if room_id is None:
                                    continue
                                if can_place(day, slot, room_id, teacher_id, sem):
                                    candidates.append((
                                        score_candidate(cid, day, slot, room_id) - 5,
                                        day,
                                        slot,
                                        room,
                                    ))
            if not candidates:
                break

            candidates.sort(key=lambda row: (-row[0],))
            _, day, slot, room = candidates[0]
            room_id = _int_or_none(room.get('id'))
            occupy({
                'day': day,
                'slot': slot,
                'room_id': room.get('id'),
                'teacher_id': teacher_id,
                'year': course.get('year'),
                'term': course.get('term'),
                'batch': course.get('batch'),
            })
            result.append({
                'day': day,
                'slot': slot,
                'room_id': room.get('id'),
                'course_code': code,
                'teacher_short_name': _norm(course.get('teacher_short_name') or course.get('teacher_short')),
                'part': _norm(course.get('part') or 'Full') or 'Full',
                'assigned_id': cid,
                'teacher_id': teacher_id or '',
                'year': _norm(course.get('year')),
                'term': _norm(course.get('term')),
                'batch': _norm(course.get('batch')),
                'color_code': _norm(course.get('color_code')),
                'is_custom': False,
                'custom_course_name': '',
            })
            placed_now += 1
            placed_count[cid] = placed_count.get(cid, 0) + 1
            course_day_used.setdefault(cid, set()).add(day)
            course_room.setdefault(cid, room_id)
            try:
                course_last_slot[cid] = (day, time_slots.index(slot))
            except ValueError:
                course_last_slot[cid] = (day, 0)
            last_day = day
            if room_cycle:
                room_cycle = room_cycle[1:] + room_cycle[:1]

        leftover = remaining - placed_now
        if leftover > 0:
            constraint_note = ''
            if prefs['prefer_days'] or prefs['avoid_days'] or prefs['time_of_day']:
                constraint_note = ' (আপনার দেওয়া সীমাবদ্ধতার কারণে স্লট কম ছিল)'
            unplaced.append({
                'course_code': code,
                'assigned_id': cid,
                'remaining': leftover,
                'reason': (
                    f'{needed} weekly slot(s) চাওয়া হয়েছিল; '
                    'teacher, room, বা একই batch/year/term কনফ্লিক্টের কারণে সব বসানো যায়নি.'
                    + constraint_note
                ),
            })

    return {
        'routine': result,
        'unplaced': unplaced,
        'explanations': explain_unplaced(unplaced),
        'preferences_applied': prefs,
    }
