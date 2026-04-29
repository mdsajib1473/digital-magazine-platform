# Agent.md: Project Specification - Unmad Digital Archive

## 1. Project Goal
Develop a digital archive website for "Unmad Magazine" where users can browse issues, and administrators can upload new magazines via the Django admin panel. This is an MVP (Minimum Viable Product).

## 2. Tech Stack
- **Backend:** Django 5.x
- **Database:** PostgreSQL (Use SQLite for local development)
- **Frontend:** Tailwind CSS
- **File Storage:** Local Media Storage

## 3. Core Features (MVP Scope)
- **User Authentication:** Only registered users can view magazine details or read PDFs.
- **Issue Management:** Admin can upload magazine title, issue number, cover photo, and PDF.
- **Landing Page:** Display a list of the latest issues and a search bar.
- **Detail View:** Single page for specific magazine details and a PDF viewer.

## 4. Database Models (Architecture)
We will create two Django apps: `accounts` and `magazines`.

### App: accounts
- **CustomUser** (Extend AbstractUser)
    - `phone_number` (CharField, optional)
    - `is_premium` (BooleanField, default=False)

### App: magazines
- **Category**
    - `name` (CharField)
- **Issue**
    - `title` (CharField)
    - `issue_number` (PositiveIntegerField)
    - `cover_image` (ImageField)
    - `pdf_file` (FileField)
    - `category` (ForeignKey to Category)
    - `published_date` (DateField)
    - `description` (TextField)
    - `is_free` (BooleanField, default=True)

## 5. Directory Structure
```text
unmad_web/
├── core/ (Settings, WSGI, ASGI)
├── apps/
│   ├── accounts/
│   └── magazines/
├── templates/
├── static/
└── media/