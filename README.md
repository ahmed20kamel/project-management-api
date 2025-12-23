# Backend - Multi-Tenant SaaS System

هذا المجلد يحتوي على تطبيق Django REST Framework للمشروع.

## 📁 Structure

```
backend/
├── backend/            # Django project settings
├── apps/               # Django applications
│   ├── authentication/ # Auth & User Management
│   └── projects/       # Project Management
├── media/              # User-uploaded files
├── requirements.txt    # Python dependencies
└── manage.py           # Django management script
```

## 🚀 Getting Started

### Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Development Server

```bash
python manage.py runserver
```

## 📚 Documentation

- [Project Structure](../PROJECT_STRUCTURE.md)
- [Organization Plan](../ORGANIZATION_PLAN.md)

## 🎯 Features

- ✅ Multi-tenant architecture
- ✅ JWT authentication
- ✅ Role-based access control
- ✅ RESTful API
- ✅ File upload support
- ✅ Audit logging

## 🛠️ Tech Stack

- **Django** - Web framework
- **Django REST Framework** - API framework
- **djangorestframework-simplejwt** - JWT authentication
- **Pillow** - Image processing
- **SQLite** - Database (development)

## 🔧 Management Commands

```bash
# Create super admin
python manage.py create_super_admin

# Setup base users
python manage.py setup_base_users

# Setup company roles
python manage.py setup_company_roles
```

