# 🤝 কন্ট্রিবিউশন গাইড

আমাদের Academic Management System প্রজেক্টে কন্ট্রিবিউট করার জন্য আপনাকে স্বাগতম! এই গাইডটি আপনাকে প্রজেক্টে অবদান রাখার জন্য প্রয়োজনীয় তথ্য প্রদান করবে।

## 📋 কন্ট্রিবিউশনের ধরন

### 🐛 Bug Reports
- অ্যাপ্লিকেশনে পাওয়া সমস্যাগুলি রিপোর্ট করুন
- স্পষ্টভাবে সমস্যাটি বর্ণনা করুন
- Error messages এবং screenshots যোগ করুন

### ✨ Feature Requests
- নতুন ফিচার প্রস্তাব করুন
- ফিচারের প্রয়োজনীয়তা ব্যাখ্যা করুন
- সম্ভাব্য implementation ideas দিন

### 📚 Documentation
- README ফাইল আপডেট করুন
- Code comments যোগ করুন
- Tutorial এবং guides লিখুন

### 🔧 Code Contributions
- Bug fixes করুন
- নতুন ফিচার যোগ করুন
- Code optimization করুন
- Tests যোগ করুন

## 🚀 শুরু করার জন্য

### 1. Repository Fork করুন
1. GitHub এ প্রজেক্টের main page এ যান
2. "Fork" বাটন ক্লিক করুন
3. আপনার GitHub account এ fork করুন

### 2. Local Clone করুন
```bash
git clone https://github.com/YOUR_USERNAME/academic-management-system.git
cd academic-management-system
```

### 3. Development Environment সেটআপ করুন
```bash
# Virtual environment তৈরি করুন
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# অথবা
venv\Scripts\activate  # Windows

# Dependencies ইনস্টল করুন
pip install -r requirements.txt

# Database সেটআপ করুন
python init_db.py
python create_admin.py
```

### 4. Feature Branch তৈরি করুন
```bash
git checkout -b feature/your-feature-name
# অথবা
git checkout -b fix/your-bug-fix
```

## 📝 Development Guidelines

### Code Style
- **Python**: PEP 8 অনুসরণ করুন
- **HTML**: Proper indentation ব্যবহার করুন
- **CSS**: Consistent naming convention
- **JavaScript**: ES6+ syntax ব্যবহার করুন

### File Structure
```
academic-management-system/
├── app.py                          # Main application
├── models.py                       # Database models
├── blueprints/                     # Flask blueprints
│   ├── auth/                       # Authentication
│   ├── class_management/           # Class management
│   ├── result_management/          # Result management
│   └── routine_management/         # Routine management
├── templates/                      # HTML templates
├── static/                         # CSS, JS, Images
└── tests/                          # Test files
```

### Database Changes
নতুন database changes এর জন্য:
1. **Model** আপডেট করুন
2. **Migration** তৈরি করুন
3. **Template** আপডেট করুন
4. **Tests** যোগ করুন

### Testing
```bash
# Unit tests
python -m pytest tests/

# Integration tests
python -m pytest tests/integration/

# Coverage report
python -m pytest --cov=app tests/
```

## 🔄 Pull Request Process

### 1. Code Changes করুন
- আপনার feature/bug fix implement করুন
- Tests যোগ করুন
- Documentation আপডেট করুন

### 2. Commit করুন
```bash
git add .
git commit -m "Add: brief description of changes"
```

### 3. Push করুন
```bash
git push origin feature/your-feature-name
```

### 4. Pull Request তৈরি করুন
1. GitHub এ আপনার fork এ যান
2. "Compare & pull request" ক্লিক করুন
3. Title এবং description লিখুন
4. Labels যোগ করুন
5. Submit করুন

### 5. Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Code refactoring

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Screenshots (if applicable)
Add screenshots here

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
```

## 🏷️ Issue Labels

### Bug Reports
- `bug` - Software bug
- `critical` - Critical bug
- `ui/ux` - User interface issue
- `performance` - Performance issue

### Feature Requests
- `enhancement` - New feature request
- `good first issue` - Good for beginners
- `help wanted` - Help needed

### Documentation
- `documentation` - Documentation update
- `readme` - README update

## 📞 যোগাযোগ

### GitHub Issues
- **Bug Reports**: Issues ট্যাবে নতুন issue তৈরি করুন
- **Feature Requests**: Enhancement label সহ issue তৈরি করুন
- **Questions**: Discussion ট্যাব ব্যবহার করুন

### Code Review
- **Review Process**: Maintainers code review করবে
- **Feedback**: Constructive feedback দিন
- **Iteration**: প্রয়োজন হলে changes করুন

## 🎯 Best Practices

### Code Quality
- ✅ **Readable code** - স্পষ্ট এবং বোধগম্য কোড লিখুন
- ✅ **Comments** - জটিল logic এর জন্য comments দিন
- ✅ **Error handling** - Proper error handling করুন
- ✅ **Security** - Security best practices অনুসরণ করুন

### Git Workflow
- ✅ **Small commits** - ছোট ছোট logical commits করুন
- ✅ **Clear messages** - স্পষ্ট commit messages লিখুন
- ✅ **Branch naming** - Descriptive branch names ব্যবহার করুন
- ✅ **Rebase** - Main branch এর সাথে sync রাখুন

### Testing
- ✅ **Unit tests** - Individual functions test করুন
- ✅ **Integration tests** - Module integration test করুন
- ✅ **Edge cases** - Boundary conditions test করুন
- ✅ **Error scenarios** - Error cases test করুন

## 🏆 Recognition

### Contributors
- **Code Contributors**: GitHub contributors list এ নাম থাকবে
- **Documentation**: README তে credit দেওয়া হবে
- **Special Thanks**: Significant contributions এর জন্য

### Contribution Levels
- **Bronze**: 1-5 contributions
- **Silver**: 6-15 contributions
- **Gold**: 16+ contributions
- **Platinum**: Core maintainer level

## 📚 Resources

### Documentation
- **Flask Docs**: https://flask.palletsprojects.com/
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/
- **Bootstrap Docs**: https://getbootstrap.com/docs/

### Tools
- **Git**: https://git-scm.com/
- **Python**: https://www.python.org/
- **VS Code**: https://code.visualstudio.com/

## 🙏 ধন্যবাদ

আপনার কন্ট্রিবিউশনের জন্য ধন্যবাদ! আপনার অবদান এই প্রজেক্টকে আরও ভালো করতে সাহায্য করবে।

---

**আপনার Academic Management System এর উন্নতিতে অংশগ্রহণ করার জন্য আবারও ধন্যবাদ!** 🎓 