"""Orchestrate full and per-part Course Outline AI generation."""
from datetime import date

from extensions import db
from utils.ai.calendar_utils import resolve_semester_dates
from utils.ai.client import AIClientError, generate_outline_json_with_meta
from utils.ai.context_builder import build_outline_context, find_best_course_for_session
from utils.ai.job_service import (
    create_outline_job,
    job_to_response,
    log_generation_call,
    normalize_parts,
)
from utils.ai.models import AIOutlineGenerationJob
from utils.ai.curriculum_anchor import anchor_payload_to_curriculum, validate_curriculum_ready
from utils.ai.outline_parser import extract_json_from_response, merge_outline_payloads, normalize_outline_payload, finalize_outline_payload_for_save
from utils.ai.outline_prompts import OUTLINE_PART_FIELDS, build_outline_prompt


def _prepare_generation_context(session, teacher_name='', course_data=None, curriculum=None,
                                calendar_events=None, Course=None, CurriculumYearTerm=None,
                                query_for_window=None, CourseSessionAssignment=None,
                                CourseFileUpload=None, generation_options=None):
    if course_data is None and Course is not None:
        course_data = find_best_course_for_session(
            session, Course, CurriculumYearTerm=CurriculumYearTerm, query_for_window=query_for_window,
        )
    if curriculum is None and course_data and getattr(course_data, 'curriculum', None):
        curriculum = course_data.curriculum

    if calendar_events is not None:
        semester_start, semester_end = resolve_semester_dates(
            calendar_events,
            academic_session=getattr(session, 'academic_session', '') or '',
            year=getattr(session, 'year', '') or '',
            term=getattr(session, 'term', '') or '',
        )
        if not semester_start or not semester_end:
            raise AIClientError(
                'Semester start/end not found in Academic Calendar. '
                'Add semester_start and semester_end events first.'
            )
        if semester_end <= semester_start:
            raise AIClientError('Semester end date must be after semester start date.')

    context = build_outline_context(
        session,
        course_data=course_data,
        curriculum=curriculum,
        calendar_events=calendar_events,
        teacher_name=teacher_name,
        CourseSessionAssignment=CourseSessionAssignment,
        CourseFileUpload=CourseFileUpload,
        generation_options=generation_options,
    )
    try:
        validate_curriculum_ready(context)
    except ValueError as exc:
        raise AIClientError(str(exc)) from exc
    return context, course_data, curriculum


def _apply_curriculator_hints(payload, context):
    """Add PLO mapping from Curriculator; never replace curriculum CLO text."""
    curriculator = context.get('curriculator') or {}
    suggested_mapping = curriculator.get('suggested_plo_mapping') or {}
    clos_with_plo = curriculator.get('clos_with_plo') or []

    if suggested_mapping:
        payload['plo_mapping'] = suggested_mapping
    if clos_with_plo and payload.get('clo_data'):
        for idx, clo in enumerate(payload['clo_data']):
            if idx < len(clos_with_plo) and not (clo.get('plos') or []):
                clo['plos'] = clos_with_plo[idx].get('plos') or []
    return payload


def _apply_session_defaults(payload, context):
    payload.setdefault('credit_value', str(context['course'].get('credit') or ''))
    payload.setdefault('course_type', context['course'].get('core_optional') or 'Core')
    year = context['session'].get('year') or ''
    term = context['session'].get('term') or ''
    section = context['session'].get('section') or ''
    payload.setdefault('level_term_section', f'{year} / {term} / {section}'.strip(' /'))
    return payload


def _context_summary(context, generation_options=None):
    summary = {
        'course_code': context['session'].get('course_code'),
        'semester_start': context['calendar'].get('semester_start'),
        'semester_end': context['calendar'].get('semester_end'),
        'working_days': context['calendar'].get('working_days'),
        'generated_on': date.today().isoformat(),
        'curriculator_document': (context.get('curriculator') or {}).get('document_name'),
        'rag_source_count': (context.get('uploaded_materials') or {}).get('source_count', 0),
        'delivery_type': context['session'].get('course_delivery_type'),
    }
    if generation_options:
        summary['generation_options'] = generation_options
    return summary


def generate_outline_part(context, part, prior_parts=None, session_id=None, user_id=None, job_id=None,
                          generation_options=None):
    """Generate a single outline part and return normalized payload + meta."""
    part = str(part).upper()
    if part not in OUTLINE_PART_FIELDS:
        raise ValueError(f'Invalid outline part: {part}')

    system_prompt, user_prompt = build_outline_prompt(
        context, part=part, prior_parts=prior_parts, generation_options=generation_options,
    )
    meta = None
    try:
        meta = generate_outline_json_with_meta(system_prompt, user_prompt)
        raw_json = extract_json_from_response(meta['text'])
        payload = normalize_outline_payload(raw_json)
        payload = anchor_payload_to_curriculum(payload, context)
        payload = finalize_outline_payload_for_save(payload)
        payload = _apply_curriculator_hints(payload, context)
        if session_id and user_id:
            log_generation_call(session_id, user_id, part, meta, job_id=job_id)
            db.session.commit()
        return payload, meta
    except Exception as exc:
        if session_id and user_id:
            log_generation_call(session_id, user_id, part, meta, job_id=job_id, error=exc)
            db.session.commit()
        raise


def generate_full_outline_for_session(session, teacher_name='', course_data=None, curriculum=None,
                                      calendar_events=None, Course=None, CurriculumYearTerm=None,
                                      query_for_window=None, user_id=None, parts=None, use_parts=True,
                                      CourseSessionAssignment=None, CourseFileUpload=None,
                                      generation_options=None):
    """
    Build context, call AI, return normalized payload for save_course_outline.
    When use_parts=True (default), generates A→B→C→D sequentially and merges (token-friendly).
    """
    context, course_data, curriculum = _prepare_generation_context(
        session, teacher_name=teacher_name, course_data=course_data, curriculum=curriculum,
        calendar_events=calendar_events, Course=Course, CurriculumYearTerm=CurriculumYearTerm,
        query_for_window=query_for_window,
        CourseSessionAssignment=CourseSessionAssignment,
        CourseFileUpload=CourseFileUpload,
        generation_options=generation_options,
    )
    session_id = getattr(session, 'id', None)

    part_list = normalize_parts(parts) if use_parts else ['full']
    merged_prior = {}
    part_payloads = []

    if use_parts and part_list != ['full']:
        for part in part_list:
            payload, _meta = generate_outline_part(
                context, part, prior_parts=merged_prior,
                session_id=session_id, user_id=user_id,
                generation_options=generation_options,
            )
            part_payloads.append(payload)
            merged_prior[part] = payload
        payload = merge_outline_payloads(*part_payloads)
    else:
        system_prompt, user_prompt = build_outline_prompt(
            context, part='full', generation_options=generation_options,
        )
        meta = generate_outline_json_with_meta(system_prompt, user_prompt)
        try:
            raw_json = extract_json_from_response(meta['text'])
            payload = normalize_outline_payload(raw_json)
            payload = anchor_payload_to_curriculum(payload, context)
            payload = _apply_curriculator_hints(payload, context)
            if session_id and user_id:
                log_generation_call(session_id, user_id, 'full', meta)
                db.session.commit()
        except Exception as exc:
            if session_id and user_id:
                log_generation_call(session_id, user_id, 'full', meta, error=exc)
                db.session.commit()
            raise

    payload = _apply_session_defaults(payload, context)
    payload = _apply_curriculator_hints(payload, context)
    return {
        'payload': payload,
        'context_summary': _context_summary(context, generation_options=generation_options),
    }


def start_async_outline_job(session, user_id, teacher_id=None, teacher_name='', course_data=None,
                            curriculum=None, calendar_events=None, Course=None,
                            CurriculumYearTerm=None, query_for_window=None, parts=None,
                            CourseSessionAssignment=None, CourseFileUpload=None,
                            generation_options=None):
    """Create a DB-backed job for polling-based multi-part generation."""
    context, course_data, curriculum = _prepare_generation_context(
        session, teacher_name=teacher_name, course_data=course_data, curriculum=curriculum,
        calendar_events=calendar_events, Course=Course, CurriculumYearTerm=CurriculumYearTerm,
        query_for_window=query_for_window,
        CourseSessionAssignment=CourseSessionAssignment,
        CourseFileUpload=CourseFileUpload,
        generation_options=generation_options,
    )
    summary = _context_summary(context, generation_options=generation_options)
    job = create_outline_job(
        session_id=session.id,
        user_id=user_id,
        teacher_id=teacher_id,
        parts=parts,
        context_summary=summary,
    )
    return job_to_response(job, message='Generation job started.')


def tick_async_outline_job(job, session, teacher_name='', course_data=None, curriculum=None,
                           calendar_events=None, Course=None, CurriculumYearTerm=None,
                           query_for_window=None, CourseSessionAssignment=None, CourseFileUpload=None):
    """Process the next part of an async job (one HTTP request per part)."""
    generation_options = (job.context_summary() or {}).get('generation_options')

    if job.status == AIOutlineGenerationJob.STATUS_COMPLETED:
        payload = _apply_session_defaults(job.partial_payload(), build_outline_context(
            session, course_data=course_data, curriculum=curriculum,
            calendar_events=calendar_events, teacher_name=teacher_name,
            generation_options=generation_options,
        ))
        return job_to_response(job, payload=payload)

    if job.status == AIOutlineGenerationJob.STATUS_FAILED:
        return job_to_response(job)

    parts = job.parts_list()
    if not parts:
        job.status = AIOutlineGenerationJob.STATUS_FAILED
        job.error_message = 'No parts configured for this job.'
        db.session.commit()
        return job_to_response(job)

    if job.part_index >= len(parts):
        job.status = AIOutlineGenerationJob.STATUS_COMPLETED
        db.session.commit()
        payload = job.partial_payload()
        context, _, _ = _prepare_generation_context(
            session, teacher_name=teacher_name, course_data=course_data, curriculum=curriculum,
            calendar_events=calendar_events, Course=Course, CurriculumYearTerm=CurriculumYearTerm,
            query_for_window=query_for_window,
            CourseSessionAssignment=CourseSessionAssignment,
            CourseFileUpload=CourseFileUpload,
            generation_options=generation_options,
        )
        payload = _apply_curriculator_hints(_apply_session_defaults(payload, context), context)
        return job_to_response(job, payload=payload, message='Course outline generated successfully. Review and save.')

    job.status = AIOutlineGenerationJob.STATUS_RUNNING
    db.session.commit()

    part = parts[job.part_index]
    try:
        context, course_data, curriculum = _prepare_generation_context(
            session, teacher_name=teacher_name, course_data=course_data, curriculum=curriculum,
            calendar_events=calendar_events, Course=Course, CurriculumYearTerm=CurriculumYearTerm,
            query_for_window=query_for_window,
            CourseSessionAssignment=CourseSessionAssignment,
            CourseFileUpload=CourseFileUpload,
            generation_options=generation_options,
        )
        prior_parts = {}
        flat = job.partial_payload()
        for prev_part in parts[:job.part_index]:
            prior_parts[prev_part] = {
                key: flat[key] for key in OUTLINE_PART_FIELDS.get(prev_part, []) if key in flat
            }

        payload, _meta = generate_outline_part(
            context, part, prior_parts=prior_parts,
            session_id=job.session_id, user_id=job.user_id, job_id=job.id,
            generation_options=generation_options,
        )
        merged = merge_outline_payloads(job.partial_payload(), payload)
        job.set_partial_payload(merged)
        job.part_index += 1

        if job.part_index >= len(parts):
            job.status = AIOutlineGenerationJob.STATUS_COMPLETED
            final_payload = _apply_curriculator_hints(_apply_session_defaults(merged, context), context)
            job.set_partial_payload(final_payload)
            db.session.commit()
            return job_to_response(
                job, payload=final_payload,
                message='Course outline generated successfully. Review and save.',
            )

        job.status = AIOutlineGenerationJob.STATUS_PENDING
        db.session.commit()
        progress = job.parts_list()
        return job_to_response(
            job,
            message=f'Part {part} complete ({job.part_index}/{len(progress)}). Generating next part...',
        )
    except Exception as exc:
        job.status = AIOutlineGenerationJob.STATUS_FAILED
        job.error_message = str(exc)
        db.session.commit()
        return job_to_response(job)
