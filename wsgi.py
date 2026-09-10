"""
Production WSGI entry point for gunicorn.
Vercel serverless will call this.
"""
from app import app

if __name__ == "__main__":
    app.run()
