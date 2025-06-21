# Academic Management System

A comprehensive Flask-based web application for managing academic operations at Law Discipline, Khulna University. This system provides three main modules: Class Management, Result Management, and Routine Management.

## Features

### 🎓 Class Management
- Add and manage student information
- View student lists with details
- Organize students by class and section
- Student ID and contact management

### 📊 Result Management
- Record and manage student results
- Subject-wise performance tracking
- Semester and year-wise organization
- Result analysis and reporting

### 📅 Routine Management
- Create and manage class schedules
- Weekly timetable view
- Teacher and room assignment
- Time slot management

### 🔐 User Authentication
- Secure login and registration system
- User session management
- Role-based access control

## Technology Stack

- **Backend**: Python 3.11.6, Flask
- **Database**: PostgreSQL
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Authentication**: Flask-Login
- **ORM**: SQLAlchemy

## Installation and Setup

### Prerequisites

1. **Python 3.11.6** - [Download here](https://www.python.org/downloads/)
2. **PostgreSQL** - [Download here](https://www.postgresql.org/download/)
3. **pip** (Python package manager)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd Academic-Management-System
```

### Step 2: Create Virtual Environment

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Database Setup

1. **Create PostgreSQL Database**
   ```sql
   CREATE DATABASE academic_management;
   CREATE USER academic_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE academic_management TO academic_user;
   ```

2. **Update Database Configuration**
   
   Edit `app.py` and update the database URI:
   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://academic_user:your_password@localhost/academic_management'
   ```

### Step 5: Environment Variables (Optional)

Create a `.env` file in the root directory:
```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://academic_user:your_password@localhost/academic_management
FLASK_ENV=development
```

### Step 6: Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage Guide

### 1. Registration and Login
- Visit the application homepage
- Click "Register" to create a new account
- Use your credentials to login

### 2. Class Management
- Click "Class Management" from the dashboard
- Add new students with their details
- View and manage student information

### 3. Result Management
- Access "Result Management" module
- Add student results for different subjects
- View performance analytics

### 4. Routine Management
- Navigate to "Routine Management"
- Create class schedules and timetables
- View weekly routine layout

## Database Schema

### Users Table
- `id` (Primary Key)
- `username` (Unique)
- `email` (Unique)
- `password_hash`
- `role`
- `created_at`

### Students Table
- `id` (Primary Key)
- `student_id` (Unique)
- `name`
- `email` (Unique)
- `phone`
- `class_name`
- `section`
- `created_at`

### Subjects Table
- `id` (Primary Key)
- `name`
- `code` (Unique)
- `credit`
- `created_at`

### Results Table
- `id` (Primary Key)
- `student_id` (Foreign Key)
- `subject_id` (Foreign Key)
- `marks`
- `total_marks`
- `semester`
- `year`
- `created_at`

### Class Schedules Table
- `id` (Primary Key)
- `class_name`
- `subject_id` (Foreign Key)
- `teacher_name`
- `day`
- `start_time`
- `end_time`
- `room`
- `created_at`

## API Endpoints

### Authentication
- `GET /` - Dashboard
- `GET /login` - Login page
- `POST /login` - Login form submission
- `GET /register` - Registration page
- `POST /register` - Registration form submission
- `GET /logout` - Logout

### Class Management
- `GET /class-management` - View students
- `GET /add-student` - Add student form
- `POST /add-student` - Add student submission

### Result Management
- `GET /result-management` - View results
- `GET /add-result` - Add result form
- `POST /add-result` - Add result submission

### Routine Management
- `GET /routine-management` - View schedules
- `GET /add-schedule` - Add schedule form
- `POST /add-schedule` - Add schedule submission

## Customization

### Adding New Features
1. Create new models in `app.py`
2. Add corresponding routes
3. Create templates in `templates/` directory
4. Update navigation and dashboard

### Styling
- Modify `static/css/style.css` for custom styles
- Update Bootstrap classes in templates
- Add custom JavaScript in `static/js/script.js`

### Database Modifications
- Update models in `app.py`
- Run database migrations if needed
- Update templates to reflect new fields

## Security Features

- Password hashing using Werkzeug
- Session management with Flask-Login
- CSRF protection
- Input validation and sanitization
- SQL injection prevention through SQLAlchemy

## Deployment

### Production Setup
1. Set `FLASK_ENV=production`
2. Use a production WSGI server (Gunicorn)
3. Configure reverse proxy (Nginx)
4. Set up SSL certificates
5. Configure database for production

### Using Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify PostgreSQL is running
   - Check database credentials
   - Ensure database exists

2. **Import Errors**
   - Activate virtual environment
   - Install all requirements
   - Check Python version compatibility

3. **Template Errors**
   - Verify template files exist
   - Check Jinja2 syntax
   - Ensure proper file permissions

### Logs
- Check console output for error messages
- Review Flask debug information
- Monitor database logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation

## Version History

- **v1.0.0** - Initial release with basic functionality
- **v1.1.0** - Added user authentication
- **v1.2.0** - Enhanced UI and responsive design
- **v1.3.0** - Added result management features
- **v1.4.0** - Implemented routine management

---

**Developed for Law Discipline, Khulna University** 

A comprehensive Flask-based web application for managing academic operations at Law Discipline, Khulna University. This system provides three main modules: Class Management, Result Management, and Routine Management.

## Features

### 🎓 Class Management
- Add and manage student information
- View student lists with details
- Organize students by class and section
- Student ID and contact management

### 📊 Result Management
- Record and manage student results
- Subject-wise performance tracking
- Semester and year-wise organization
- Result analysis and reporting

### 📅 Routine Management
- Create and manage class schedules
- Weekly timetable view
- Teacher and room assignment
- Time slot management

### 🔐 User Authentication
- Secure login and registration system
- User session management
- Role-based access control

## Technology Stack

- **Backend**: Python 3.11.6, Flask
- **Database**: PostgreSQL
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Authentication**: Flask-Login
- **ORM**: SQLAlchemy

## Installation and Setup

### Prerequisites

1. **Python 3.11.6** - [Download here](https://www.python.org/downloads/)
2. **PostgreSQL** - [Download here](https://www.postgresql.org/download/)
3. **pip** (Python package manager)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd Academic-Management-System
```

### Step 2: Create Virtual Environment

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Database Setup

1. **Create PostgreSQL Database**
   ```sql
   CREATE DATABASE academic_management;
   CREATE USER academic_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE academic_management TO academic_user;
   ```

2. **Update Database Configuration**
   
   Edit `app.py` and update the database URI:
   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://academic_user:your_password@localhost/academic_management'
   ```

### Step 5: Environment Variables (Optional)

Create a `.env` file in the root directory:
```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://academic_user:your_password@localhost/academic_management
FLASK_ENV=development
```

### Step 6: Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage Guide

### 1. Registration and Login
- Visit the application homepage
- Click "Register" to create a new account
- Use your credentials to login

### 2. Class Management
- Click "Class Management" from the dashboard
- Add new students with their details
- View and manage student information

### 3. Result Management
- Access "Result Management" module
- Add student results for different subjects
- View performance analytics

### 4. Routine Management
- Navigate to "Routine Management"
- Create class schedules and timetables
- View weekly routine layout

## Database Schema

### Users Table
- `id` (Primary Key)
- `username` (Unique)
- `email` (Unique)
- `password_hash`
- `role`
- `created_at`

### Students Table
- `id` (Primary Key)
- `student_id` (Unique)
- `name`
- `email` (Unique)
- `phone`
- `class_name`
- `section`
- `created_at`

### Subjects Table
- `id` (Primary Key)
- `name`
- `code` (Unique)
- `credit`
- `created_at`

### Results Table
- `id` (Primary Key)
- `student_id` (Foreign Key)
- `subject_id` (Foreign Key)
- `marks`
- `total_marks`
- `semester`
- `year`
- `created_at`

### Class Schedules Table
- `id` (Primary Key)
- `class_name`
- `subject_id` (Foreign Key)
- `teacher_name`
- `day`
- `start_time`
- `end_time`
- `room`
- `created_at`

## API Endpoints

### Authentication
- `GET /` - Dashboard
- `GET /login` - Login page
- `POST /login` - Login form submission
- `GET /register` - Registration page
- `POST /register` - Registration form submission
- `GET /logout` - Logout

### Class Management
- `GET /class-management` - View students
- `GET /add-student` - Add student form
- `POST /add-student` - Add student submission

### Result Management
- `GET /result-management` - View results
- `GET /add-result` - Add result form
- `POST /add-result` - Add result submission

### Routine Management
- `GET /routine-management` - View schedules
- `GET /add-schedule` - Add schedule form
- `POST /add-schedule` - Add schedule submission

## Customization

### Adding New Features
1. Create new models in `app.py`
2. Add corresponding routes
3. Create templates in `templates/` directory
4. Update navigation and dashboard

### Styling
- Modify `static/css/style.css` for custom styles
- Update Bootstrap classes in templates
- Add custom JavaScript in `static/js/script.js`

### Database Modifications
- Update models in `app.py`
- Run database migrations if needed
- Update templates to reflect new fields

## Security Features

- Password hashing using Werkzeug
- Session management with Flask-Login
- CSRF protection
- Input validation and sanitization
- SQL injection prevention through SQLAlchemy

## Deployment

### Production Setup
1. Set `FLASK_ENV=production`
2. Use a production WSGI server (Gunicorn)
3. Configure reverse proxy (Nginx)
4. Set up SSL certificates
5. Configure database for production

### Using Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify PostgreSQL is running
   - Check database credentials
   - Ensure database exists

2. **Import Errors**
   - Activate virtual environment
   - Install all requirements
   - Check Python version compatibility

3. **Template Errors**
   - Verify template files exist
   - Check Jinja2 syntax
   - Ensure proper file permissions

### Logs
- Check console output for error messages
- Review Flask debug information
- Monitor database logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation

## Version History

- **v1.0.0** - Initial release with basic functionality
- **v1.1.0** - Added user authentication
- **v1.2.0** - Enhanced UI and responsive design
- **v1.3.0** - Added result management features
- **v1.4.0** - Implemented routine management

---

**Developed for Law Discipline, Khulna University** 