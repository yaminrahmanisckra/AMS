"""Course lookup picks the correct curriculum when duplicate course codes exist."""
from blueprints.class_management.routes import find_course_from_curriculum
from blueprints.class_management.models import Session
from blueprints.course_management.models import (
    Course,
    CourseSessionAssignment,
    Curriculum,
    CurriculumYearTerm,
)
from extensions import db


def _seed_duplicate_courses(app, teacher_id, window_id):
    with app.app_context():
        old_curr = Curriculum(name='Old Curriculum')
        new_curr = Curriculum(name='New Curriculum')
        db.session.add_all([old_curr, new_curr])
        db.session.flush()

        old_course = Course(
            curriculum_id=old_curr.id,
            course_code='Law 4103',
            course_name='Constitutional Law',
            credit=4.0,
            course_type='Theory',
            category='ug',
            year='Third',
            term='First',
            rationale='OLD curriculum rationale',
        )
        new_course = Course(
            curriculum_id=new_curr.id,
            course_code='Law 4103',
            course_name='Constitutional Law',
            credit=4.0,
            course_type='Theory',
            category='ug',
            year='Fourth',
            term='First',
            rationale='NEW curriculum rationale',
        )
        db.session.add_all([old_course, new_course])
        db.session.flush()

        db.session.add(
            CurriculumYearTerm(
                curriculum_id=new_curr.id,
                year='Fourth',
                term='First',
                academic_session='2025-26',
                batch='28',
            )
        )

        new_session = Session(
            year='Fourth',
            term='First',
            academic_session='2025-26',
            course_code='Law 4103',
            course_name='Constitutional Law',
            teacher_id=teacher_id,
            course_type='Theory',
            category='ug',
            window_id=window_id,
        )
        db.session.add(new_session)
        db.session.flush()

        db.session.add(
            CourseSessionAssignment(
                course_id=new_course.id,
                curriculum_id=new_curr.id,
                teacher_id=teacher_id,
                year='Fourth',
                term='First',
                academic_session='2025-26',
                batch='28',
                window_id=window_id,
                session_id=new_session.id,
                session_created=True,
            )
        )
        db.session.commit()
        return new_session.id, old_course.id, new_course.id


def test_find_course_uses_csa_curriculum_not_first_match(app, teacher_user, windows):
    session_id, old_course_id, new_course_id = _seed_duplicate_courses(
        app, teacher_user['teacher_id'], windows['w1_id']
    )
    with app.app_context():
        session = Session.query.get(session_id)
        course = find_course_from_curriculum(session.course_code, session.course_name, session=session)
        assert course is not None
        assert course.id == new_course_id
        assert course.rationale == 'NEW curriculum rationale'
        assert course.id != old_course_id


def test_find_course_prefers_academic_session_without_csa(app, teacher_user, windows):
    with app.app_context():
        old_curr = Curriculum(name='Old Curriculum')
        new_curr = Curriculum(name='New Curriculum')
        db.session.add_all([old_curr, new_curr])
        db.session.flush()

        old_course = Course(
            curriculum_id=old_curr.id,
            course_code='Law 4103',
            course_name='Constitutional Law',
            credit=4.0,
            course_type='Theory',
            category='ug',
            rationale='OLD curriculum rationale',
        )
        new_course = Course(
            curriculum_id=new_curr.id,
            course_code='Law 4103',
            course_name='Constitutional Law',
            credit=4.0,
            course_type='Theory',
            category='ug',
            rationale='NEW curriculum rationale',
        )
        db.session.add_all([old_course, new_course])
        db.session.flush()

        db.session.add(
            CurriculumYearTerm(
                curriculum_id=new_curr.id,
                year='Fourth',
                term='First',
                academic_session='2025-26',
                batch='28',
            )
        )

        session = Session(
            year='Fourth',
            term='First',
            academic_session='2025-26',
            course_code='Law 4103',
            course_name='Constitutional Law',
            teacher_id=teacher_user['teacher_id'],
            course_type='Theory',
            category='ug',
            window_id=windows['w1_id'],
        )
        db.session.add(session)
        db.session.commit()

        course = find_course_from_curriculum(session.course_code, session.course_name, session=session)
        assert course is not None
        assert course.id == new_course.id
        assert course.rationale == 'NEW curriculum rationale'
