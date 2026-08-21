"""Async job orchestration for multi-part outline generation."""
import json

from extensions import db
from utils.ai.models import AIOutlineGenerationJob, AIOutlineGenerationLog


DEFAULT_PARTS = ['A', 'B', 'C', 'D']
_PART_DISPLAY = {'CD': 'C+D'}


def normalize_parts(parts):
    if not parts:
        parts = list(DEFAULT_PARTS)
    normalized = []
    for part in parts:
        key = str(part).upper().strip()
        if key == 'CD':
            if 'CD' not in normalized:
                normalized.append('CD')
            continue
        if key in ('A', 'B', 'C', 'D') and key not in normalized:
            normalized.append(key)
    if 'C' in normalized and 'D' in normalized:
        compacted = []
        inserted = False
        for item in normalized:
            if item in ('C', 'D'):
                if not inserted:
                    compacted.append('CD')
                    inserted = True
            else:
                compacted.append(item)
        normalized = compacted
    return normalized or ['A', 'B', 'CD']


def create_outline_job(session_id, user_id, teacher_id=None, parts=None, context_summary=None):
    job = AIOutlineGenerationJob(
        session_id=session_id,
        user_id=user_id,
        teacher_id=teacher_id,
        parts_json=json.dumps(normalize_parts(parts)),
        part_index=0,
        status=AIOutlineGenerationJob.STATUS_PENDING,
    )
    if context_summary:
        job.set_context_summary(context_summary)
    db.session.add(job)
    db.session.commit()
    return job


def job_progress(job):
    parts = job.parts_list()
    total = len(parts)
    done = min(job.part_index, total)
    current = parts[job.part_index] if job.part_index < total else None
    current_label = _PART_DISPLAY.get(current, current)
    return {
        'total': total,
        'done': done,
        'current_part': current_label,
        'label': f'{done}/{total}',
    }


def job_to_response(job, payload=None, message=None):
    progress = job_progress(job)
    response = {
        'success': job.status != AIOutlineGenerationJob.STATUS_FAILED,
        'job_id': job.id,
        'status': job.status,
        'progress': progress,
        'message': message or '',
        'context_summary': job.context_summary(),
    }
    if job.status == AIOutlineGenerationJob.STATUS_FAILED:
        response['success'] = False
        response['message'] = job.error_message or 'Generation failed'
    if job.status == AIOutlineGenerationJob.STATUS_COMPLETED and payload is not None:
        from utils.ai.outline_parser import finalize_outline_payload_for_save
        payload = finalize_outline_payload_for_save(payload)
        response['payload'] = payload
        response['message'] = message or 'Course outline generated successfully. Review and save.'
    elif job.status == AIOutlineGenerationJob.STATUS_COMPLETED:
        from utils.ai.outline_parser import finalize_outline_payload_for_save
        response['payload'] = finalize_outline_payload_for_save(job.partial_payload())
        response['message'] = message or 'Course outline generated successfully. Review and save.'
    return response


def log_generation_call(session_id, user_id, part, meta, job_id=None, error=None):
    from utils.ai.cost_utils import estimate_cost_usd

    usage = (meta or {}).get('usage') or {}
    prompt_tokens = usage.get('prompt_tokens')
    completion_tokens = usage.get('completion_tokens')
    model_name = (meta or {}).get('model_name')
    row = AIOutlineGenerationLog(
        job_id=job_id,
        session_id=session_id,
        user_id=user_id,
        part=part or 'full',
        provider=(meta or {}).get('provider'),
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=usage.get('total_tokens'),
        estimated_cost_usd=estimate_cost_usd(model_name, prompt_tokens, completion_tokens),
        duration_ms=(meta or {}).get('duration_ms'),
        status=AIOutlineGenerationLog.STATUS_ERROR if error else AIOutlineGenerationLog.STATUS_SUCCESS,
        error_message=str(error)[:2000] if error else None,
    )
    db.session.add(row)
    return row
