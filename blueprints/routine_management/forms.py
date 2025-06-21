from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, FloatField
from wtforms.validators import DataRequired, Length

class TeacherForm(FlaskForm):
    name = StringField('Teacher Name', validators=[DataRequired(), Length(min=2, max=100)])
    short_name = StringField('Short Name (Callsign)', validators=[DataRequired(), Length(min=1, max=10)])
    submit = SubmitField('Add Teacher')

class CourseForm(FlaskForm):
    course_code = StringField('Course Code', validators=[DataRequired(), Length(min=3, max=20)])
    course_name = StringField('Course Name', validators=[DataRequired(), Length(min=3, max=100)])
    credit = FloatField('Credit', validators=[DataRequired()])
    course_type = SelectField('Type', choices=[('Theory', 'Theory'), ('Sessional', 'Sessional')], validators=[DataRequired()])
    category = SelectField('Category', choices=[('ug', 'Undergraduate'), ('pg', 'Postgraduate')], default='ug', validators=[DataRequired()])
    submit = SubmitField('Add Course')

class RoomForm(FlaskForm):
    room_number = StringField('Room Number', validators=[DataRequired(), Length(min=1, max=20)])
    submit = SubmitField('Add Room')

class AssignCourseForm(FlaskForm):
    teacher = SelectField('Teacher', coerce=int, validators=[DataRequired()])
    course = SelectField('Course', coerce=int, validators=[DataRequired()])
    part = SelectField('Course Part', validators=[DataRequired()])
    submit = SubmitField('Assign Course')
