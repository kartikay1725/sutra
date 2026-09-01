$env:DATABASE_URL="sqlite:///d:/sutra/backend/e2e.db"
$env:JWT_SECRET="dev-only-change-this-before-production"
$env:EVENT_INTEGRITY_KEY="3626d9575eef92212420df28d3d51de891bbf6c1541d70a686b5df7b2c7f91c5"
$env:APP_ENV="development"

# Init DB
d:\sutra\.venv\Scripts\python init_db.py

# Start uvicorn
d:\sutra\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
