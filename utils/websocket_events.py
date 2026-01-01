"""
WebSocket event utilities for emitting real-time updates to connected clients.
"""

from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request


# Global socketio instance - will be initialized in app.py
socketio = None


def init_socketio(socketio_instance):
    """Initialize the global socketio instance."""
    global socketio
    socketio = socketio_instance


def emit_attendance_update(session_id, attendance_data):
    """
    Emit attendance update event to all clients viewing the session.
    
    Args:
        session_id: The session ID
        attendance_data: Dictionary with attendance update information
    """
    if socketio:
        socketio.emit('attendance_updated', {
            'session_id': session_id,
            'data': attendance_data
        }, room=f'session_{session_id}', namespace='/')


def emit_assessment_update(session_id, assessment_data):
    """
    Emit assessment update event to all clients viewing the session.
    
    Args:
        session_id: The session ID
        assessment_data: Dictionary with assessment update information
    """
    if socketio:
        socketio.emit('assessment_updated', {
            'session_id': session_id,
            'data': assessment_data
        }, room=f'session_{session_id}', namespace='/')


def emit_course_outline_update(session_id, outline_data):
    """
    Emit course outline update event to all clients viewing the session.
    
    Args:
        session_id: The session ID
        outline_data: Dictionary with course outline update information
    """
    if socketio:
        socketio.emit('course_outline_updated', {
            'session_id': session_id,
            'data': outline_data
        }, room=f'session_{session_id}', namespace='/')


def emit_session_created(session_data):
    """
    Emit session created event to all connected clients.
    
    Args:
        session_data: Dictionary with session information
    """
    if socketio:
        socketio.emit('session_created', {
            'data': session_data
        }, namespace='/', broadcast=True)


def emit_marks_update(session_id, marks_data):
    """
    Emit marks update event to all clients viewing the session.
    
    Args:
        session_id: The session ID (result session)
        marks_data: Dictionary with marks update information
    """
    if socketio:
        socketio.emit('marks_updated', {
            'session_id': session_id,
            'data': marks_data
        }, room=f'result_session_{session_id}', namespace='/')


def emit_result_updated(result_data):
    """
    Emit result update event to all connected clients.
    
    Args:
        result_data: Dictionary with result update information
    """
    if socketio:
        socketio.emit('result_updated', {
            'data': result_data
        }, namespace='/', broadcast=True)


def emit_routine_updated(routine_data=None):
    """
    Emit routine update event to all connected clients.
    
    Args:
        routine_data: Optional dictionary with routine update information
    """
    if socketio:
        socketio.emit('routine_updated', {
            'data': routine_data or {}
        }, namespace='/', broadcast=True)


def emit_course_updated(course_data):
    """
    Emit course/curriculum update event to all connected clients.
    
    Args:
        course_data: Dictionary with course update information
    """
    if socketio:
        socketio.emit('course_updated', {
            'data': course_data
        }, namespace='/', broadcast=True)


def emit_student_updated(student_data):
    """
    Emit student update event to all connected clients.
    
    Args:
        student_data: Dictionary with student update information
    """
    if socketio:
        socketio.emit('student_updated', {
            'data': student_data
        }, namespace='/', broadcast=True)

