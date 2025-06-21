# Academic Management System (AMS)

A comprehensive web-based academic management system built with Flask, designed to streamline educational institution operations including student management, class management, result management, and routine management.

## Features

### 🔐 Authentication System
- User registration and login
- Role-based access control
- Secure password management

### 👥 Student Management
- Add, edit, and delete student records
- Student profile management
- Student search and filtering

### 📚 Class Management
- Create and manage classes
- Assign teachers to classes
- Class schedule management
- Assessment tracking

### 📊 Result Management
- Add and manage student marks
- Generate result reports
- Academic session management
- Performance analytics

### 📅 Routine Management
- Create and manage class routines
- Course assignment
- Schedule optimization
- Time table generation

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy with PostgreSQL
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Authentication**: Flask-Login
- **Forms**: WTForms
- **Database Migration**: Alembic
- **PDF Generation**: ReportLab
- **Excel Handling**: OpenPyXL

## Installation

### Prerequisites
- Python 3.8 or higher
- PostgreSQL database
- pip (Python package installer)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yaminrahmanisckra/AMS.git
   cd AMS
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=postgresql://username:password@localhost/ams_db
   ```

5. **Initialize database**
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

6. **Create admin user**
   ```bash
   python create_admin.py
   ```

7. **Run the application**
   ```bash
   flask run
   ```

The application will be available at `http://localhost:5000`

## Project Structure

```
AMS/
├── app.py                 # Main application file
├── extensions.py          # Flask extensions configuration
├── create_admin.py        # Admin user creation script
├── blueprints/            # Application blueprints
│   ├── auth/             # Authentication module
│   ├── class_management/  # Class management module
│   ├── result_management/ # Result management module
│   └── routine_management/ # Routine management module
├── static/               # Static files (CSS, JS, images)
├── templates/            # HTML templates
├── migrations/           # Database migration files
├── uploads/             # File upload directory
└── instance/            # Instance-specific files
```

## Usage

### Admin Access
- Login with admin credentials
- Access all modules and features
- Manage users and system settings

### Teacher Access
- View assigned classes
- Manage student results
- Access routine information

### Student Access
- View personal information
- Check results and grades
- Access class schedules

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Yamin Rahman Isckra**
- GitHub: [@yaminrahmanisckra](https://github.com/yaminrahmanisckra)

## Support

For support and questions, please open an issue on GitHub or contact the development team.

## Acknowledgments

- Flask community for the excellent web framework
- Bootstrap team for the responsive UI components
- All contributors and testers of this project