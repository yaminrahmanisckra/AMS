"""Condensed few-shot examples for KU Law Discipline course outlines."""

# Abbreviated excerpts — style and structure reference for the model.

EXAMPLE_PART_A = {
    'course_objectives': [
        'Explain the historical development of constitutional law in Bangladesh.',
        'Analyze landmark judgments of the Supreme Court on fundamental rights.',
        'Apply constitutional principles to contemporary governance issues.',
    ],
    'course_summary': (
        'This course introduces students to the constitutional framework of Bangladesh, '
        'including the structure of government, fundamental rights, and judicial review. '
        'It builds analytical skills through case studies and comparative readings.'
    ),
    'prerequisites': 'Introduction to Law (LAW1101) or equivalent.',
    'contact_hours': '3 hours per week (lecture + discussion)',
    'cie_marks': '40',
    'smee_marks': '60',
    'credit_value': '3',
    'course_type': 'Core',
    'level_term_section': 'Third Year / First Term / A',
    'clo_data': [
        {'number': 1, 'description': 'Explain the basic structure and sources of constitutional law.', 'plos': ['PLO 1', 'PLO 3']},
        {'number': 2, 'description': 'Analyze constitutional provisions relating to fundamental rights.', 'plos': ['PLO 2', 'PLO 5']},
    ],
    'plo_mapping': {
        'CLO 1': {'PLO 1': 3, 'PLO 3': 2},
        'CLO 2': {'PLO 2': 3, 'PLO 5': 2},
    },
}

EXAMPLE_PART_B = {
    'course_content_summary': {
        'sectionA': [
            {'topic': 'Introduction to Constitutional Law', 'selected': True, 'num_classes': 2},
            {'topic': 'Sources and Basic Structure', 'selected': True, 'num_classes': 3},
        ],
        'sectionB': [
            {'topic': 'Fundamental Rights: Articles 27–44', 'selected': True, 'num_classes': 4},
            {'topic': 'Judicial Review and Writ Jurisdiction', 'selected': True, 'num_classes': 3},
        ],
    },
    'lesson_plan': [
        {
            'week': 'Week 1',
            'date': '5-9 January 2025',
            'topic': 'Introduction to Constitutional Law',
            'outcome': 'Students will define constitutional law and identify its sources.',
            'activities': 'Assigned reading; class discussion on constitutional sources',
            'teaching_assessment': 'Lecture, Socratic discussion',
            'clo_alignment': 'CLO 1',
        },
        {
            'week': 'Week 1',
            'date': '5-9 January 2025',
            'topic': 'Sources of the Constitution',
            'outcome': 'Students will identify constitutional sources.',
            'activities': 'Assigned reading; source-mapping exercise',
            'teaching_assessment': 'Lecture, discussion',
            'clo_alignment': 'CLO 1',
        },
        {
            'week': 'Week 2',
            'date': '12-16 January 2025',
            'topic': 'Fundamental Rights Overview',
            'outcome': 'Students will classify fundamental rights under the Constitution.',
            'activities': 'Case reading; group rights-mapping exercise',
            'teaching_assessment': 'Case briefing, group presentation',
            'clo_alignment': 'CLO 2',
        },
    ],
    'cie_breakdown': [
        {'category': 'Attendance', 'marks': 5},
        {'category': 'Class Test 1', 'marks': 15},
        {'category': 'Assignment', 'marks': 20},
    ],
    'smee_breakdown': [
        {'category': 'Written Examination', 'marks': 60},
    ],
}

EXAMPLE_PART_C = {
    'assessment_strategy': {
        'attendance_percentage': 5,
        'ca_percentage': 35,
        'final_exam_percentage': 60,
        'attendance_marks': 5,
        'ca_section_a_total': 2,
        'ca_section_b_total': 2,
    },
    'assessment_techniques': [
        {'strategy': 'Attendance', 'total_marks': 5, 'clo1': 5, 'clo2': 5},
        {'strategy': 'Class Test', 'total_marks': 15, 'clo1': 10, 'clo2': 15},
        {'strategy': 'Final Examination', 'total_marks': 60, 'clo1': 30, 'clo2': 60},
    ],
    'rubrics': [
        {
            'type': 'Assignment',
            'criteria': 'Legal analysis and citation',
            'excellent': 'Clear thesis with authoritative sources',
            'good': 'Adequate analysis with minor citation gaps',
            'satisfactory': 'Basic understanding shown',
            'poor': 'Insufficient legal reasoning',
        },
    ],
    'grading_policy': [
        {'range': '80-100', 'grade': 'A+'},
        {'range': '75-79', 'grade': 'A'},
        {'range': '70-74', 'grade': 'A-'},
    ],
    'evaluation_policy': {
        'grading_system': 'Letter grades per KU Law Discipline policy',
        'make_up_procedures': 'Make-up exams only with approved medical or official leave.',
    },
    'make_up_procedures': 'Students must apply to the Head within 7 days of absence with supporting documents.',
}

EXAMPLE_PART_D = {
    'textbooks': [
        'Mahmudul Islam, Constitutional Law of Bangladesh (latest ed.)',
    ],
    'reference_books': [
        'Kesavananda Bharati v. State of Kerala (1973) — selected excerpts',
        'Bangladesh Legal Materials (KU Law Discipline course pack)',
    ],
    'other_resources': [
        'Supreme Court of Bangladesh website — recent judgments',
        'KU Law Discipline Moodle / LMS materials',
    ],
    'course_file_components': [
        'Syllabus and lesson plan',
        'Assessment rubrics',
        'Sample examination questions',
    ],
    'other_issues': {
        'class_discussion': 'Active participation is expected; respectful debate is encouraged.',
        'general_expectations': 'Students must complete assigned readings before class.',
        'communication': 'Contact instructor during office hours or via official email.',
        'academic_honesty': 'Plagiarism and unauthorized assistance are strictly prohibited.',
    },
}

FEW_SHOT_BY_PART = {
    'A': EXAMPLE_PART_A,
    'B': EXAMPLE_PART_B,
    'C': EXAMPLE_PART_C,
    'D': EXAMPLE_PART_D,
}
