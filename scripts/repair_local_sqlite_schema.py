#!/usr/bin/env python3
"""Apply missing SQLite columns when Alembic history is out of sync (local dev only)."""
import os
import sqlite3

BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(BASEDIR, 'instance', 'academic_management.db')

# table -> list of (column_name, alter_table_suffix)
PATCHES = {
    'student_course_registration': [
        ('source_year', 'source_year VARCHAR(20)'),
        ('source_term', 'source_term VARCHAR(20)'),
        ('relevant_course_id', 'relevant_course_id INTEGER'),
        ('relevant_course_code', 'relevant_course_code VARCHAR(50)'),
        ('relevant_academic_session', 'relevant_academic_session VARCHAR(50)'),
        ('relevant_year', 'relevant_year VARCHAR(20)'),
        ('relevant_term', 'relevant_term VARCHAR(20)'),
        ('window_id', 'window_id INTEGER REFERENCES operational_window(id)'),
        ('use_relevant_for_committee', 'use_relevant_for_committee BOOLEAN NOT NULL DEFAULT 1'),
    ],
    'duty_assignment': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'session_archive': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'exam_paper_evaluation': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'exam_scrutinizer_invite': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'exam_paper_evaluator_assignment': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'remuneration_form': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'result_session': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'saved_routine': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'routine': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'routine_time_slot': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'assigned_course': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'course_registration_invite': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'academic_calendar_event': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'psac_committee': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'survey_link': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'course_session_assignment': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'class_session': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'active_semester_config': [('window_id', 'window_id INTEGER REFERENCES operational_window(id)')],
    'class_attendance': [
        ('slot_number', 'slot_number INTEGER'),
        ('status', "status VARCHAR(20) NOT NULL DEFAULT 'present'"),
    ],
    'course_question_message': [
        ('seen_by_student_at', 'seen_by_student_at DATETIME'),
        ('seen_by_teacher_at', 'seen_by_teacher_at DATETIME'),
    ],
    'course_question_thread': [
        ('teacher_read_at', 'teacher_read_at DATETIME'),
    ],
    'student_feedback_response': [
        ('is_read', 'is_read BOOLEAN NOT NULL DEFAULT 0'),
    ],
    'survey_response': [
        ('is_read', 'is_read BOOLEAN NOT NULL DEFAULT 0'),
        ('is_starred', 'is_starred BOOLEAN NOT NULL DEFAULT 0'),
    ],
    'alumni_survey_response': [
        ('contributions', 'contributions JSON'),
        ('is_read', 'is_read BOOLEAN NOT NULL DEFAULT 0'),
        ('is_starred', 'is_starred BOOLEAN NOT NULL DEFAULT 0'),
    ],
}

WINDOW_BACKFILL_TABLES = [
    'duty_assignment', 'session_archive', 'exam_paper_evaluation', 'exam_scrutinizer_invite',
    'exam_paper_evaluator_assignment', 'remuneration_form', 'result_session',
    'saved_routine', 'routine', 'routine_time_slot', 'assigned_course',
    'course_registration_invite', 'academic_calendar_event', 'psac_committee', 'survey_link',
    'course_session_assignment', 'class_session', 'student_course_registration', 'active_semester_config',
]


def table_exists(cur, name):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def table_columns(cur, name):
    cur.execute(f'PRAGMA table_info({name})')
    return {row[1] for row in cur.fetchall()}


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f'Database not found: {DB_PATH}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    added = []

    for table, columns in PATCHES.items():
        if not table_exists(cur, table):
            continue
        existing = table_columns(cur, table)
        for col_name, ddl in columns:
            if col_name in existing:
                continue
            cur.execute(f'ALTER TABLE {table} ADD COLUMN {ddl}')
            added.append(f'{table}.{col_name}')

    for table in WINDOW_BACKFILL_TABLES:
        if not table_exists(cur, table):
            continue
        if 'window_id' not in table_columns(cur, table):
            continue
        cur.execute(f'UPDATE {table} SET window_id = 1 WHERE window_id IS NULL')

    if table_exists(cur, 'course_registration_invite') and table_exists(cur, 'student_course_registration'):
        cur.execute('''
            UPDATE course_registration_invite
            SET window_id = (
                SELECT scr.window_id FROM student_course_registration scr
                WHERE scr.id = course_registration_invite.registration_id
            )
            WHERE registration_id IS NOT NULL
              AND window_id IS NULL
        ''')

    if table_exists(cur, 'survey_link') and table_exists(cur, 'psac_committee'):
        cur.execute('''
            UPDATE survey_link
            SET window_id = (
                SELECT pc.window_id FROM psac_committee pc
                WHERE pc.id = survey_link.committee_id
            )
            WHERE committee_id IS NOT NULL AND window_id IS NULL
        ''')

    cur.execute('DELETE FROM alembic_version')
    cur.execute("INSERT INTO alembic_version (version_num) VALUES ('g7b8c9d0e1f2')")

    conn.commit()
    conn.close()

    if added:
        print('Added columns:')
        for item in added:
            print(f'  - {item}')
    else:
        print('No columns needed; schema already up to date.')
    print(f'Database: {DB_PATH}')


if __name__ == '__main__':
    main()
