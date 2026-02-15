# B2B Pharmacy Surgical Product Distribution System (MVP)

A web-based B2B system for surgical product distribution.

## Tech Stack
- **Backend:** Python, Django, DRF, PostgreSQL (SQLite for local), JWT, WeasyPrint
- **Frontend:** React, Ant Design, Axios, Vite

## Setup Instructions

### Backend
1. Create a virtual environment: `python -m venv venv`
2. Activate it: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Run migrations: `cd backend && python manage.py migrate`
5. Create superuser: `python manage.py createsuperuser`
6. Start server: `python manage.py runserver`

### Frontend
1. Navigate to frontend: `cd frontend`
2. Install dependencies: `npm install`
3. Start dev server: `npm run dev`

## Features
- Public product browsing and search.
- Pharmacy registration and secure login (JWT).
- Cart and Order placement for pharmacies.
- Admin dashboard with stats, order approval, and product management.
- Automatic stock reduction on order approval.
- Automated Invoice PDF generation using WeasyPrint.

## Credentials
- **Admin:** `admin` / `adminpassword` (Created by setup script)
