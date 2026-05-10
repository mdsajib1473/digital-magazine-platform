# Agent.md: Project Specification - Digital Magazine Archive

## 1. Project Goal & Philosophy
Develop a premium, highly secure digital archive for magazines. The core philosophy is to provide a physical-magazine-like reading experience in the browser while strictly preventing piracy (PDF downloading) using advanced evasion techniques against download managers like IDM.

## 2. Tech Stack & Infrastructure
- **Backend:** Django 5.x (Python)
- **Database:** SQLite (Local Dev) -> PostgreSQL (Production on AWS)
- **Frontend:** HTML, Tailwind CSS (via PostCSS/CDN), Vanilla JS
- **File Storage:** Local Media (Dev) -> AWS S3 (Production)
- **Hosting/Deployment:** AWS (EC2/Elastic Beanstalk)
- **Admin Theme:** Django-Jazzmin

## 3. Core Features & Business Logic
- **Authentication:** Custom Tailwind UI. Users are logged in directly immediately after Signup (no email verification needed). Password reset flow via email.
- **Business Model (Pay-per-issue):** Users purchase individual magazines via SSLCommerz payment gateway.
- **Search & Filter:** Users can search by Title and filter by Month & Year.
- **Library Dashboard:** A dedicated page where users can see only the issues they have successfully purchased.
- **Secure PDF Reader (The Masterpiece):**
  - Uses strictly **PDF.js** (Client-side Canvas rendering) with 2.5x High-DPI supersampling for crisp Bengali text.
  - Reader always starts from Page 1 (no progress saving).
  - **Anti-Piracy (IDM-Proof):** The `/pdf/` endpoint uses **Byte-XOR Masking** (`PDF_XOR_KEY = 0xAA`). The Django view streams the XOR-masked bytes. The JS client fetches it as an `ArrayBuffer`, applies the reverse XOR mask, and passes it to PDF.js.
  - **Endpoint Sealing:** Direct hits to the PDF URL without `?client=pdfjs` return a `403 Forbidden`. Anonymous users get a `302 Redirect` to login.
  - Right-click, text selection, and drag-and-drop are completely disabled on the reader page.

## 4. Database Architecture

### App: accounts
- **CustomUser** (Extend AbstractUser)
    - `phone_number` (CharField, optional)

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
    - `price` (DecimalField/IntegerField, default=0)
    - `description` (TextField)
    - `is_free` (BooleanField, default=False)
- **Purchase** (NEW - To track user ownership)
    - `user` (ForeignKey to CustomUser)
    - `issue` (ForeignKey to Issue)
    - `payment_status` (CharField: Pending, Success, Failed)
    - `transaction_id` (CharField, unique)
    - `purchased_at` (DateTimeField, auto_now_add=True)

## 5. Development Rules for AI Agent
- **Never alter the XOR Masking or `devicePixelRatio` logic in the reader** without explicit permission.
- **Styling:** Always use Tailwind utility classes. Maintain the padding, gray/white contrast, and shadow aesthetic established in `_auth_card.html`.
- **Forms:** Render Django forms manually using Tailwind classes rather than `{{ form.as_p }}` to ensure UI consistency.
- **Test Backend Email:** Keep `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'` for local testing.