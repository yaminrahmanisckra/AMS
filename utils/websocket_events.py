"""Live-update helpers.

Socket.IO is disabled (cPanel/Passenger does not usefully support it).
These functions stay as no-ops so existing route call sites keep working.
"""


def init_socketio(socketio_instance=None):
    return None


def emit_attendance_update(session_id, attendance_data):
    return None


def emit_assessment_update(session_id, assessment_data):
    return None


def emit_course_outline_update(session_id, outline_data):
    return None


def emit_session_created(session_data):
    return None


def emit_marks_update(session_id, marks_data):
    return None


def emit_result_updated(result_data):
    return None


def emit_routine_updated(routine_data=None):
    return None


def emit_course_updated(course_data):
    return None


def emit_student_updated(student_data):
    return None
