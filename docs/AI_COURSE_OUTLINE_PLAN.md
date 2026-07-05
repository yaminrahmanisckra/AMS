# AI Course Outline Generation — Implementation Plan

## Goal
Admin configures AI provider + API key; teachers click **Generate Full Outline with AI** on the Course Outline edit page. The system builds context from Curriculum, Academic Calendar (working days), and session metadata, calls the AI, validates JSON, shows preview, and fills Part A–D fields.

## Architecture

```
Admin (ai_settings) → encrypted API key in DB
Teacher clicks Generate → context_builder → AI client → outline_parser → preview → save_course_outline JSON
```

## Phases

### Phase 1 — Foundation (this sprint)
- [x] `AIProviderSetting` model + migration
- [x] `utils/ai/encryption.py` — Fernet encrypt/decrypt API keys
- [x] Admin page `/admin/ai-settings`
- [x] `utils/ai/client.py` — OpenAI, Gemini, Anthropic, DeepSeek adapters
- [x] `utils/ai/context_builder.py` — session → course → curriculum + calendar
- [x] `utils/ai/outline_prompts.py` + `outline_parser.py`
- [x] Route `POST .../outline/generate-full-ai`
- [x] UI button + preview modal on `edit_course_outline.html`

### Phase 2 — Quality (follow-up)
- [x] Few-shot examples from real KU Law outlines in prompt
- [x] Per-part generation (A only, B only) for token limits
- [x] Generation log + cost tracking
- [x] Async/background job for slow cPanel hosts (DB job + browser polling)

### Phase 3 — Advanced (optional)
- [x] RAG from uploaded course files
- [x] PLO mapping from Curriculator documents
- [x] Batch generate for all sessions in a semester

## Data sources for AI context

| Source | Fields used |
|--------|-------------|
| `Session` | course_code, course_name, year, term, academic_session, batch |
| `Course` | rationale, clo, content_section_a/b, credit, course_type |
| `Curriculum` | applicable batches (window-scoped) |
| `AcademicCalendarEvent` | semester_start/end, holidays |
| Working days | Sun–Thu minus holidays + Fri/Sat excluded |

## Output schema
Matches `save_course_outline()` JSON keys (Part A–D).

## Security
- API keys encrypted at rest (Fernet + SECRET_KEY-derived key)
- Admin-only settings page
- Teacher preview before save; never auto-publish without confirmation
