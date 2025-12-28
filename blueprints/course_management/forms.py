from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, FloatField, SelectMultipleField, TextAreaField
from wtforms.validators import DataRequired, Length

class CurriculumForm(FlaskForm):
    name = StringField('Curriculum Name', validators=[DataRequired(), Length(min=3, max=100)])
    date = StringField('Date', validators=[DataRequired(), Length(max=50)], render_kw={'placeholder': 'e.g., 15 January 2025'})
    applicable_batches = SelectMultipleField('Applicable for', choices=[], coerce=str, validators=[DataRequired()])
    submit = SubmitField('Add Curriculum')

class CourseForm(FlaskForm):
    course_code = StringField('Course Code', validators=[DataRequired(), Length(min=3, max=20)])
    course_name = StringField('Course Name', validators=[DataRequired(), Length(min=3, max=100)])
    credit = FloatField('Credit', validators=[DataRequired()])
    course_type = SelectField('Type', choices=[
        ('Theory', 'Theory'), 
        ('Sessional', 'Sessional'), 
        ('Viva', 'Viva'),
        ('Thesis (UG)', 'Thesis (UG)'),
        ('Thesis I (UG)', 'Thesis I (UG)'),
        ('Thesis II (UG)', 'Thesis II (UG)'),
        ('Dissertation Proposal (PG)', 'Dissertation Proposal (PG)'),
        ('Dissertation Defence (PG)', 'Dissertation Defence (PG)')
    ], validators=[DataRequired()])
    category = SelectField('Category', choices=[('ug', 'Undergraduate'), ('pg', 'Postgraduate')], default='ug', validators=[DataRequired()])
    core_optional = SelectField('Core/Optional', choices=[('Core', 'Core'), ('Optional', 'Optional')], validators=[DataRequired()])
    year = StringField('Year', validators=[Length(max=50)], render_kw={'placeholder': 'Auto-filled from course code', 'readonly': True})
    term = StringField('Term', validators=[Length(max=50)], render_kw={'placeholder': 'Auto-filled from course code', 'readonly': True})
    submit = SubmitField('Add Course')

class CourseInfoForm(FlaskForm):
    year = StringField('Year', validators=[Length(max=50)], render_kw={'placeholder': 'e.g., 1st Year, 2nd Year'})
    term = StringField('Term', validators=[Length(max=50)], render_kw={'placeholder': 'e.g., 1st Term, 2nd Term'})
    rationale = TextAreaField('Rationale', validators=[Length(max=2000)], render_kw={'rows': 5})
    clos_json = StringField('CLOs JSON')  # Hidden field to store JSON string of CLOs
    content_section_a = TextAreaField('Content Section A', validators=[Length(max=2000)], render_kw={'rows': 5})
    content_section_b = TextAreaField('Content Section B', validators=[Length(max=2000)], render_kw={'rows': 5})
    submit = SubmitField('Save Information')

