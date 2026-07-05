#!/usr/bin/env python3
"""Add {% block mobile_title %} to templates extending base.html."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_PATTERNS = (
    "_pdf.html",
    "weasyprint",
    "print_",
)

# Path substring -> mobile title (checked in order; first match wins)
TITLE_RULES: list[tuple[str, str]] = [
    ("class_management/assessment", "Assessment"),
    ("class_management/take_attendance", "Attendance"),
    ("class_management/view_attendance", "Attendance"),
    ("class_management/evaluation_course_assessment_form", "Observation"),
    ("class_management/evaluation_course_assessment", "Evaluation"),
    ("class_management/evaluation_course_review", "Review"),
    ("class_management/evaluation_course_assessment_view", "Evaluation"),
    ("class_management/evaluation", "Evaluation"),
    ("class_management/question_bank", "Questions"),
    ("class_management/students_list", "Students"),
    ("class_management/course_questions", "Questions"),
    ("class_management/course_file", "Course File"),
    ("class_management/student_course_files", "Course Files"),
    ("class_management/student_view_scores", "Scores"),
    ("class_management/student_notifications", "Notifications"),
    ("class_management/student_feedback_manage", "Feedback"),
    ("class_management/invitations", "Invitations"),
    ("class_management/edit_course_outline", "Outline"),
    ("class_management/edit_session", "Edit Session"),
    ("class_management/archive", "Archive"),
    ("class_management/index", "Classes"),
    ("exam_evaluation_marks", "Marks"),
    ("exam_evaluation_scrutinizer", "Scrutinizer"),
    ("exam_evaluation_edit", "Exam Eval"),
    ("exam_evaluation", "Exam Eval"),
    ("result_management/rm_add_marks", "Add Marks"),
    ("result_management/rm_add_subject", "Add Subject"),
    ("result_management/rm_add_session", "Add Session"),
    ("result_management/rm_add_student", "Add Student"),
    ("result_management/rm_edit_student", "Edit Student"),
    ("result_management/rm_view_results", "Results"),
    ("result_management/rm_student_wise_result", "Results"),
    ("result_management/rm_course_wise_result", "Results"),
    ("result_management/rm_course_registration", "Registration"),
    ("result_management/rm_archive", "Archive"),
    ("result_management/rm_index", "Results"),
    ("course_management/coordinator_register", "Register"),
    ("course_management/coordinator_registration", "Registration"),
    ("course_management/student_registration", "Registration"),
    ("course_management/index", "Courses"),
    ("student_management/edit_student", "Edit Student"),
    ("student_management/index", "Students"),
    ("academic_calendar/add_batch_event", "Add Event"),
    ("academic_calendar/edit_batch_event", "Edit Event"),
    ("academic_calendar/batch_events_student", "Events"),
    ("academic_calendar/batch_events_teacher", "Events"),
    ("academic_calendar/assessment_schedule", "Schedule"),
    ("academic_calendar/add_event", "Add Event"),
    ("academic_calendar/edit_event", "Edit Event"),
    ("academic_calendar/index", "Calendar"),
    ("routine_management/routine_new", "Routine"),
    ("routine_management/public_routines", "Routines"),
    ("routine_management/index", "Routine"),
    ("curriculator/document_create", "New Doc"),
    ("curriculator/document_detail", "Document"),
    ("curriculator/document_import", "Import"),
    ("curriculator/part_a_section_edit", "Edit Section"),
    ("curriculator/part_view", "Document"),
    ("curriculator/permissions", "Permissions"),
    ("curriculator/export", "Export"),
    ("curriculator/index", "Curriculum"),
    ("self_assessment/employer_survey", "Survey"),
    ("self_assessment/student_survey", "Survey"),
    ("self_assessment/non_academic_survey", "Survey"),
    ("self_assessment/faculty_survey", "Survey"),
    ("self_assessment/alumni_survey", "Survey"),
    ("self_assessment/psac_committee", "PSAC"),
    ("self_assessment/response_view", "Response"),
    ("self_assessment/responses_list", "Responses"),
    ("self_assessment/survey_success", "Survey"),
    ("self_assessment/survey_invalid", "Survey"),
    ("self_assessment/survey_already_submitted", "Survey"),
    ("self_assessment/survey_placeholder", "Survey"),
    ("self_assessment/index", "Surveys"),
    ("leave_application/form_sick_other", "Leave"),
    ("leave_application/form_special", "Leave"),
    ("leave_application/form_non_numeric_station", "Leave"),
    ("leave_application/form_station", "Leave"),
    ("leave_application/form_casual_station", "Leave"),
    ("leave_application/index", "Leave"),
    ("exam_committee_management", "Exam Committee"),
    ("exam_committee_chief/custom_remuneration", "Remuneration"),
    ("exam_committee_chief/dashboard", "Chief"),
    ("exam_committee_member/dashboard", "Member"),
    ("head/exam_committee_archive", "Archive"),
    ("head/assign_duties", "Duties"),
    ("head/session_archive", "Archive"),
    ("head/dashboard", "Head"),
    ("officer/exam_info", "Exam Info"),
    ("admin/active_semester", "Semester"),
    ("admin/active_window", "Window"),
    ("admin_dashboard", "Admin"),
    ("admin_edit_user", "Edit User"),
    ("admin_reset_password", "Reset Password"),
    ("remuneration_list", "Remuneration"),
    ("remuneration_placeholder", "Remuneration"),
    ("student_feedback_form", "Feedback"),
    ("student/dashboard", "Student"),
    ("auth/no_active_window", "Window"),
    ("auth/select_window", "Window"),
    ("auth/forgot_password", "Password"),
    ("auth/reset_password", "Password"),
    ("profile", "Profile"),
    ("dashboard", "Dashboard"),
]

DEFAULT_TITLES = {
    "index.html": "Home",
    "dashboard.html": "Dashboard",
}


def infer_title(path: Path, content: str) -> str:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    for needle, title in TITLE_RULES:
        if needle in rel:
            return title
    if path.name in DEFAULT_TITLES:
        return DEFAULT_TITLES[path.name]
    title_match = re.search(
        r"\{%\s*block\s+title\s*%\}(.*?)\{%\s*endblock\s*%\}",
        content,
        re.DOTALL,
    )
    if title_match:
        raw = re.sub(r"\{%.*?%\}", "", title_match.group(1)).strip()
        raw = re.sub(r"\s+", " ", raw)
        if raw and len(raw) <= 24:
            return raw[:24]
        if raw:
            words = raw.split()[:2]
            return " ".join(words)[:24]
    stem = path.stem.replace("_", " ").title()
    return stem[:24] if stem else "Page"


def extends_base(content: str) -> bool:
    return bool(
        re.search(
            r'\{%\s*extends\s+["\']base\.html["\']\s*%\}',
            content,
        )
    )


def has_mobile_title(content: str) -> bool:
    return bool(re.search(r"\{%\s*block\s+mobile_title\s*%\}", content))


def insert_mobile_title(content: str, title: str) -> str:
    block = f"{{% block mobile_title %}}{title}{{% endblock %}}\n"
    if has_mobile_title(content):
        return content

    # After title block if present
    title_block = re.search(
        r"(\{%\s*block\s+title\s*%\}.*?\{%\s*endblock\s*%\}\n)",
        content,
        re.DOTALL,
    )
    if title_block:
        end = title_block.end()
        return content[:end] + "\n" + block + content[end:]

    # After extends line
    extends = re.search(
        r"(\{%\s*extends\s+[\"']base\.html[\"']\s*%\}\n)",
        content,
    )
    if extends:
        end = extends.end()
        return content[:end] + block + content[end:]

    return block + content


def main() -> None:
    updated: list[str] = []
    skipped: list[str] = []

    for path in sorted(ROOT.rglob("*.html")):
        rel = str(path.relative_to(ROOT))
        if rel == "templates/base.html":
            continue
        if any(p in rel for p in SKIP_PATTERNS):
            continue

        content = path.read_text(encoding="utf-8")
        if not extends_base(content):
            continue
        if has_mobile_title(content):
            skipped.append(rel)
            continue

        title = infer_title(path, content)
        new_content = insert_mobile_title(content, title)
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            updated.append(f"{rel} -> {title}")

    print(f"Updated {len(updated)} templates:")
    for line in updated:
        print(f"  {line}")
    print(f"Skipped (already had mobile_title): {len(skipped)}")


if __name__ == "__main__":
    main()
