import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Never enable debug mode in production - exposes stack traces and allows code execution
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
    app.run(debug=debug_mode)
