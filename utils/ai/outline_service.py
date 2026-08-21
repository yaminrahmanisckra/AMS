"""Orchestrate full and per-part Course Outline AI generation."""
from datetime import date

from extensions import db
from utils.ai.calendar_utils import resolve_semester_dates
from utils.ai.client import AIClientError, generate_outline_json_with_meta, user_facing_generation_error
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
from utils.ai.local_fill import (
    fill_part_a_from_context,
    fill_part_b_locally,
    fill_part_c_locally,
    fill_part_cd_locally,
    fill_part_d_locally,
    merge_weekly_notes_into_skeleton,
)
from utils.ai.outline_prompts import OUTLINE_PART_FIELDS, PART_MAX_TOKENS, build_outline_prompt
from utils.ai.session_utils import reset_db_session


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


def _log_generation_safely(session_id, user_id, part, meta, job_id=None, error=None):
    """Write the generation log without masking the original AI error."""
    if not session_id or not user_id:
        return
    try:
        reset_db_session()
        log_meta = meta
        if error and not log_meta:
            try:
                from utils.ai.client import get_active_provider_setting
                cfg = get_active_provider_setting()
                log_meta = {'provider': cfg.get('provider'), 'model_name': cfg.get('model_name')}
            except Exception:
                log_meta = None
        log_generation_call(
            session_id, user_id, part, log_meta, job_id=job_id,
            error=user_facing_generation_error(error) if error else None,
        )
        db.session.commit()
    except Exception as log_exc:
        try:
            from flask import current_app
            current_app.logger.warning('AI generation log failed: %s', log_exc)
        except Exception:
            pass
        reset_db_session()


def _detail_level(generation_options):
    return ((generation_options or {}).get('detail_level') or 'standard').strip().lower()


def part_needs_ai(part, generation_options=None):
    part = str(part or '').upper()
    if part == 'A':
        return False
    if part == 'B' and _detail_level(generation_options) == 'concise':
        return False
    return True


def generate_outline_part(context, part, prior_parts=None, session_id=None, user_id=None, job_id=None,
                          generation_options=None):
    """Generate a single outline part and return normalized payload + meta."""
    part = str(part).upper()
    if part not in OUTLINE_PART_FIELDS:
        raise ValueError(f'Invalid outline part: {part}')

    if part == 'A':
        payload = fill_part_a_from_context(context, generation_options)
        payload = anchor_payload_to_curriculum(payload, context, generation_options)
        payload = finalize_outline_payload_for_save(payload)
        payload = _apply_curriculator_hints(payload, context)
        meta = {
            'text': '',
            'provider': 'local',
            'model_name': 'curriculum',
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
            'duration_ms': 0,
        }
        _log_generation_safely(session_id, user_id, part, meta, job_id=job_id)
        return payload, meta

    if part == 'B':
        local_b = fill_part_b_locally(context, generation_options)
        if not part_needs_ai(part, generation_options):
            payload = anchor_payload_to_curriculum(local_b, context, generation_options)
            payload = finalize_outline_payload_for_save(payload)
            meta = {
                'text': '',
                'provider': 'local',
                'model_name': 'calendar',
                'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
                'duration_ms': 0,
            }
            _log_generation_safely(session_id, user_id, part, meta, job_id=job_id)
            return payload, meta

        system_prompt, user_prompt = build_outline_prompt(
            context, part=part, prior_parts=prior_parts, generation_options=generation_options,
        )
        meta = None
        try:
            meta = generate_outline_json_with_meta(
                system_prompt, user_prompt, max_tokens=PART_MAX_TOKENS.get(part),
            )
            raw_json = extract_json_from_response(meta['text'])
            weeks = []
            if isinstance(raw_json, dict):
                weeks = raw_json.get('weeks') or raw_json.get('lesson_plan') or []
            payload = dict(local_b)
            payload['lesson_plan'] = merge_weekly_notes_into_skeleton(
                local_b['lesson_plan'], weeks, generation_options=generation_options,
            )
            if isinstance(raw_json, dict):
                if raw_json.get('cie_breakdown'):
                    payload['cie_breakdown'] = raw_json['cie_breakdown']
                if raw_json.get('smee_breakdown'):
                    payload['smee_breakdown'] = raw_json['smee_breakdown']
            payload = normalize_outline_payload(payload)
            payload = anchor_payload_to_curriculum(payload, context, generation_options)
            payload = finalize_outline_payload_for_save(payload)
            _log_generation_safely(session_id, user_id, part, meta, job_id=job_id)
            return payload, meta
        except Exception as exc:
            _log_generation_safely(session_id, user_id, part, meta, job_id=job_id, error=exc)
            payload = anchor_payload_to_curriculum(local_b, context, generation_options)
            payload = finalize_outline_payload_for_save(payload)
            fallback_meta = meta or {
                'text': '',
                'provider': 'local',
                'model_name': 'calendar-fallback',
                'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
                'duration_ms': 0,
            }
            return payload, fallback_meta

    local_cd = None
    if part == 'CD':
        local_cd = fill_part_cd_locally(context, generation_options)
    elif part == 'C':
        local_cd = fill_part_c_locally(context, generation_options)
    elif part == 'D':
        local_cd = fill_part_d_locally(context, generation_options)

    system_prompt, user_prompt = build_outline_prompt(
        context, part=part, prior_parts=prior_parts, generation_options=generation_options,
    )
    meta = None
    try:
        meta = generate_outline_json_with_meta(
            system_prompt, user_prompt, max_tokens=PART_MAX_TOKENS.get(part),
        )
        raw_json = extract_json_from_response(meta['text'])
        payload = normalize_outline_payload(raw_json)
        if local_cd:
            payload = {**local_cd, **{k: v for k, v in payload.items() if v not in (None, '', [], {})}}
        payload = anchor_payload_to_curriculum(payload, context, generation_options)
        payload = finalize_outline_payload_for_save(payload)
        payload = _apply_curriculator_hints(payload, context)
        _log_generation_safely(session_id, user_id, part, meta, job_id=job_id)
        return payload, meta
    except Exception as exc:
        _log_generation_safely(session_id, user_id, part, meta, job_id=job_id, error=exc)
        if local_cd:
            payload = anchor_payload_to_curriculum(local_cd, context, generation_options)
            payload = finalize_outline_payload_for_save(payload)
            payload = _apply_curriculator_hints(payload, context)
            return payload, meta or {
                'text': '',
                'provider': 'local',
                'model_name': 'template-fallback',
                'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
                'duration_ms': 0,
            }
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
        meta = generate_outline_json_with_meta(
            system_prompt, user_prompt, max_tokens=PART_MAX_TOKENS.get('full'),
        )
        try:
            raw_json = extract_json_from_response(meta['text'])
            payload = normalize_outline_payload(raw_json)
            payload = anchor_payload_to_curriculum(payload, context, generation_options)
            payload = _apply_curriculator_hints(payload, context)
            _log_generation_safely(session_id, user_id, 'full', meta)
        except Exception as exc:
            _log_generation_safely(session_id, user_id, 'full', meta, error=exc)
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
    job_id = job.id
    session_id = job.session_id
    user_id = job.user_id

    try:
        context, course_data, curriculum = _prepare_generation_context(
            session, teacher_name=teacher_name, course_data=course_data, curriculum=curriculum,
            calendar_events=calendar_events, Course=Course, CurriculumYearTerm=CurriculumYearTerm,
            query_for_window=query_for_window,
            CourseSessionAssignment=CourseSessionAssignment,
            CourseFileUpload=CourseFileUpload,
            generation_options=generation_options,
        )
        last_part = parts[job.part_index]
        while job.part_index < len(parts):
            part = parts[job.part_index]
            last_part = part
            prior_parts = {}
            flat = job.partial_payload()
            for prev_part in parts[:job.part_index]:
                prior_parts[prev_part] = {
                    key: flat[key] for key in OUTLINE_PART_FIELDS.get(prev_part, []) if key in flat
                }

            payload, _meta = generate_outline_part(
                context, part, prior_parts=prior_parts,
                session_id=session_id, user_id=user_id, job_id=job_id,
                generation_options=generation_options,
            )
            job = AIOutlineGenerationJob.query.get(job_id)
            if not job:
                raise AIClientError('Generation job was lost. Please try again.')
            merged = merge_outline_payloads(job.partial_payload(), payload)
            job.set_partial_payload(merged)
            job.part_index += 1
            db.session.commit()
            used_ai = part_needs_ai(part, generation_options)

            if job.part_index >= len(parts):
                job.status = AIOutlineGenerationJob.STATUS_COMPLETED
                final_payload = _apply_curriculator_hints(_apply_session_defaults(merged, context), context)
                job.set_partial_payload(final_payload)
                db.session.commit()
                return job_to_response(
                    job, payload=final_payload,
                    message='Course outline generated successfully. Review and save.',
                )

            if used_ai:
                break

        job.status = AIOutlineGenerationJob.STATUS_PENDING
        db.session.commit()
        progress = job.parts_list()
        shown = {'CD': 'C+D'}.get(last_part, last_part)
        return job_to_response(
            job,
            message=f'Part {shown} complete ({job.part_index}/{len(progress)}). Generating next part...',
        )
    except Exception as exc:
        reset_db_session()
        message = user_facing_generation_error(exc)
        try:
            job = AIOutlineGenerationJob.query.get(job_id)
            if job:
                job.status = AIOutlineGenerationJob.STATUS_FAILED
                job.error_message = message
                db.session.commit()
                return job_to_response(job)
        except Exception:
            reset_db_session()
        return {
            'success': False,
            'job_id': job_id,
            'status': AIOutlineGenerationJob.STATUS_FAILED,
            'message': message,
        }
