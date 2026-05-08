# Unmad Digital Archive

**Live Demo:** [https://unmad-bd.onrender.com](https://unmad-bd.onrender.com)

## Project Overview

The Unmad Digital Archive is a web application that preserves and makes accessible decades of the beloved Bangladeshi comic magazine "Unmad." This project transforms physical issues into a browsable, searchable digital library, allowing readers to explore the rich history of Bangladeshi satire and cartoon art from anywhere in the world. Each issue is carefully digitized, catalogued, and presented in a reader-friendly interface that honors the original magazine's aesthetic while leveraging modern web technologies for accessibility and performance.

## Features

### User-Facing Features

Browse the complete archive of Unmad magazine issues organized chronologically. Each issue entry displays a high-quality cover image, publication date, and title. Users can access issues marked as "Free" without any barriers, while premium issues require a one-time purchase through the integrated payment gateway. The PDF reader offers a clean, distraction-free reading experience with page navigation controls. Users can create accounts to track their purchased issues in a personal library, manage their profile, and reset passwords via email. The responsive design ensures seamless access across desktop, tablet, and mobile devices.

### Admin Features

Administrators have full control over the archive through a modern, jazzmin-styled Django admin panel. The admin interface allows creating, editing, and deleting magazine issues with cover image uploads and PDF file management. Purchase records are tracked with detailed information including payment status, transaction IDs, timestamps, and user associations. The admin can manage user accounts, view purchase history, and monitor transaction statuses. The SSLCommerz payment integration provides automated handling of successful, failed, and cancelled payment callbacks with hash validation for security.

## Screenshots

![Homepage](screenshots/Homepage.png)

![PDF Reader](screenshots/pdf_reader.png)

![Admin Panel](screenshots/admin_panel.png)

## Tech Stack

The project is built with Django 5.2 as the web framework, using PostgreSQL hosted on Supabase as the primary database. Media files are stored on Supabase S3-compatible storage with a dual-bucket architecture for security. The application is deployed on Render, a cloud platform that provides automatic HTTPS, managed PostgreSQL, and continuous deployment from the GitHub repository. The frontend uses Tailwind CSS for styling with a custom dark red and black color scheme that reflects the Unmad brand. WhiteNoise serves static files in production with gzip and brotli compression for optimal performance. Payment processing is handled through the SSLCommerz gateway with sandbox mode for development and live mode for production transactions.


## Project Structure
A brief overview of the core directory structure:

* `apps/` : Contains all Django applications (e.g., magazines, users, payments).
* `core/` : The main Django project configuration directory (settings, urls, wsgi).
* `theme/` : Tailwind CSS configuration and compiled assets.
* `templates/` : Global HTML templates and base layouts.
* `static/` : Static files (images, JS, raw CSS) served by WhiteNoise.
* `screenshots/` : Images used for this documentation.
* `build.sh` : Deployment script for Render.

## Architecture Highlights

The storage architecture employs a secure dual-bucket system on Supabase S3. Cover images reside in a public bucket with unrestricted read access, allowing browsers to cache and serve them efficiently without authentication overhead. PDF files are stored in a private bucket that requires signed URLs for access. Django-storages generates time-limited, cryptographically signed URLs for PDF downloads, ensuring that only authorized users who have purchased an issue can access its content. These signed URLs expire after a configurable period (default 3600 seconds), preventing unauthorized sharing. The system uses path-style addressing to communicate with Supabase's S3-compatible endpoint and generates public URLs in the native Supabase format for optimal browser compatibility. This architecture balances performance with security, providing fast cover image loading while protecting premium content.

## Local Development Setup

### Prerequisites

Python 3.11 or higher, Node.js and npm for Tailwind CSS compilation, and Git for version control.

### Step 1: Clone the Repository

Clone the project from GitHub and navigate into the directory:

```bash
git clone https://github.com/mdsajib1473/Unmad_magazine-website.git
cd Unmad_magazine-website
```

### Step 2: Create a Virtual Environment

Create and activate a Python virtual environment:

On Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

On macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

Install all required Python packages from requirements.txt:

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the project root and add the following configuration:

```
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost

# Database (local SQLite for development)
# DATABASE_URL=postgres://user:password@host:5432/dbname

# Supabase Storage (set USE_SUPABASE_STORAGE=True to enable cloud storage)
USE_SUPABASE_STORAGE=False
SUPABASE_S3_ENDPOINT_URL=https://your-project-ref.storage.supabase.co/storage/v1/s3
SUPABASE_S3_REGION=ap-southeast-1
SUPABASE_S3_ACCESS_KEY_ID=your-access-key
SUPABASE_S3_SECRET_ACCESS_KEY=your-secret-key
SUPABASE_PUBLIC_BUCKET=unmad-archive
SUPABASE_PRIVATE_BUCKET=unmad-archive-pdfs
SUPABASE_SIGNED_URL_EXPIRE=3600

# SSLCommerz Payment Gateway
SSLCOMMERZ_STORE_ID=your-store-id
SSLCOMMERZ_STORE_PASSWORD=your-store-password
SSLCOMMERZ_IS_SANDBOX=True
```

For local development, you can skip the Supabase and SSLCommerz variables initially. The application will fall back to local SQLite database and file system storage.

### Step 5: Run Migrations

Apply the database migrations to create the necessary tables:

```bash
python manage.py migrate
```

### Step 6: Create a Superuser

Create an admin account to access the Django admin panel:

```bash
python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password.

### Step 7: Build Tailwind CSS

Compile the Tailwind CSS for development:

```bash
python manage.py tailwind build
```

### Step 8: Start the Development Server

Run the Django development server:

```bash
python manage.py runserver
```

The application will be available at http://127.0.0.1:8000. Access the admin panel at http://127.0.0.1:8000/admin using the superuser credentials created in Step 6.

### Step 9: Load Sample Data (Optional)

If you have a data dump file, you can load it into the database:

```bash
python manage.py loaddata dump.json
```

This will populate the database with existing issues, users, and purchase records.
