"""Batch AI outline generation for all sessions in a semester."""
import json

from extensions import db
from utils.ai.models import AIOutlineBatchJob, AIOutlineGenerationJob
from utils.ai.outline_service import start_async_outline_job


def list_sessions_for_semester(academic_session, year, term, batch=None, query_for_window=None,
                               Session=None, CourseSessionAssignment=None):
    """Return non-archived sessions matching semester filters."""
    if not Session:
        return []

    query = Session.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        archived=False,
    )
    if query_for_window:
        query = query_for_window(Session).filter(
            Session.academic_session == academic_session,
            Session.year == year,
            Session.term == term,
            Session.archived.is_(False),
        )

    if batch and CourseSessionAssignment:
        session_ids = [
            row.session_id for row in CourseSessionAssignment.query.filter_by(
                academic_session=academic_session,
                year=year,
                term=term,
                batch=batch,
            ).all()
            if row.session_id
        ]
        if not session_ids:
            return []
        query = query.filter(Session.id.in_(session_ids))

    return query.order_by(Session.course_code.asc(), Session.id.asc()).all()


def create_batch_outline_jobs(user_id, academic_session, year, term, batch=None, parts=None,
                              query_for_window=None, Session=None, CourseSessionAssignment=None,
                              Course=None, CurriculumYearTerm=None, calendar_events=None,
                              find_course_from_curriculum=None, teacher_id=None,
                              CourseFileUpload=None):
    """Create one async outline job per matching session."""
    sessions = list_sessions_for_semester(
        academic_session, year, term, batch=batch,
        query_for_window=query_for_window, Session=Session,
        CourseSessionAssignment=CourseSessionAssignment,
    )
    if not sessions:
        raise ValueError('No class sessions found for the selected semester.')

    batch_job = AIOutlineBatchJob(
        user_id=user_id,
        academic_session=academic_session,
        year=year,
        term=term,
        batch=batch,
        status=AIOutlineBatchJob.STATUS_RUNNING,
    )
    batch_job.set_items_list([])
    db.session.add(batch_job)
    db.session.flush()

    items = []
    for session in sessions:
        course_data = find_course_from_curriculum(session.course_code, session.course_name) if find_course_from_curriculum else None
        curriculum = course_data.curriculum if course_data and getattr(course_data, 'curriculum', None) else None
        teacher_name = ''
        if getattr(session, 'teacher', None):
            teacher_name = session.teacher.name

        job_response = start_async_outline_job(
            session,
            user_id=user_id,
            teacher_id=teacher_id,
            teacher_name=teacher_name,
            course_data=course_data,
            curriculum=curriculum,
            calendar_events=calendar_events,
            Course=Course,
            CurriculumYearTerm=CurriculumYearTerm,
            query_for_window=query_for_window,
            parts=parts,
            CourseSessionAssignment=CourseSessionAssignment,
            CourseFileUpload=CourseFileUpload,
        )
        items.append({
            'session_id': session.id,
            'job_id': job_response['job_id'],
            'course_code': session.course_code,
            'course_name': session.course_name,
            'status': job_response.get('status', AIOutlineGenerationJob.STATUS_PENDING),
        })

    batch_job.set_items_list(items)
    batch_job.status = AIOutlineBatchJob.STATUS_RUNNING
    db.session.commit()
    return batch_job, items


def refresh_batch_job_status(batch_job):
    """Update child job statuses on a batch job."""
    items = batch_job.items_list()
    changed = False
    for item in items:
        job = AIOutlineGenerationJob.query.get(item.get('job_id'))
        if not job:
            continue
        new_status = job.status
        if item.get('status') != new_status:
            item['status'] = new_status
            changed = True

    if changed:
        batch_job.set_items_list(items)

    statuses = [item.get('status') for item in items]
    if statuses and all(s == AIOutlineGenerationJob.STATUS_COMPLETED for s in statuses):
        batch_job.status = AIOutlineBatchJob.STATUS_COMPLETED
    elif any(s == AIOutlineGenerationJob.STATUS_FAILED for s in statuses):
        batch_job.status = AIOutlineBatchJob.STATUS_FAILED
        batch_job.error_message = 'One or more session jobs failed.'
    else:
        batch_job.status = AIOutlineBatchJob.STATUS_RUNNING

    db.session.commit()
    return batch_job


def batch_job_to_response(batch_job):
    refresh_batch_job_status(batch_job)
    items = batch_job.items_list()
    total = len(items)
    done = sum(1 for item in items if item.get('status') == AIOutlineGenerationJob.STATUS_COMPLETED)
    failed = sum(1 for item in items if item.get('status') == AIOutlineGenerationJob.STATUS_FAILED)
    return {
        'success': batch_job.status != AIOutlineBatchJob.STATUS_FAILED,
        'batch_job_id': batch_job.id,
        'status': batch_job.status,
        'message': batch_job.error_message or '',
        'progress': {
            'total': total,
            'done': done,
            'failed': failed,
            'label': f'{done}/{total}',
        },
        'items': items,
        'filters': {
            'academic_session': batch_job.academic_session,
            'year': batch_job.year,
            'term': batch_job.term,
            'batch': batch_job.batch,
        },
    }
