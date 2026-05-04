# Roadmap.md: Unmad BD

## Phase 1: Auth Completion & User Profile (Current)
*   **Password Reset Flow:** Django templates and logic for password recovery.
*   **User Profile Page:** Basic profile management (Name, Phone, Password update).

## Phase 2: E-Commerce & User Library (Core Logic)
*   **Purchase Model Update:** Implement the `Purchase` tracking model.
*   **Payment Gateway Integration:** SSLCommerz Sandbox (Test mode is completely free).
*   **My Library Dashboard:** UI for users to access purchased magazines.
*   **Reader Access Control:** Lock down `/read/` and `/pdf/` based on `Purchase` records.

## Phase 3: Production Prep (The "Zero-Budget" Cloud Shift)
*   **Database Migration (Free):** Shift from local SQLite to **Supabase PostgreSQL** (Free Tier: 500MB).
*   **Media Storage (Free):** Shift local PDFs and Cover Images to **Supabase Storage** (Free Tier: 1GB).
*   *Crucial Test:* Verify XOR Masking and PDF.js speed with Supabase cloud URLs.

## Phase 4: Deployment & Go-Live (MVP Launch)
*   **Hosting (Free):** Deploy the Django backend on **Render.com** (Free Web Service).
*   **Domain (Free initially):** Start with the free Render subdomain (e.g., `unmad-bd.onrender.com`). Once revenue starts coming in, purchase a `.com` or `.com.bd` domain.
*   **Live Payment:** Switch SSLCommerz from Sandbox to Live mode.
*   **Final Testing & Launch:** Complete a real transaction, verify the secure reader, and share the platform with the first users!