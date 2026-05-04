"""
app.py — Flask Application Entry Point

HOW REQUESTS FLOW:
  Browser → CORS check → Blueprint route → @require_role decorator
  → auth_service.get_current_user() → Firebase token verification
  → Supabase query (via service key) → JSON response

BLUEPRINTS AND THEIR PREFIX:
  /api/auth/*       → routes/auth.py          (register, login, Google, me)
  /api/*            → routes/public.py        (specialties, doctors, slots — no auth)
  /api/appointments → routes/appointments.py  (book, my appointments)
  /api/doctor/*     → routes/doctor_dashboard.py (doctor role only)
  /api/admin/*      → routes/admin_dashboard.py  (admin role only)

STATIC FILES:
  /           → serves index.html from the project root (parent of backend/)
  /<file>.html → serves that HTML file from the project root
  /static/*   → serves backend/static/* (api.js, etc.)

RUN:
  python3 app.py
  gunicorn -w 4 -b 0.0.0.0:8080 app:app   (production)
"""
import os
import logging
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import Config

# The HTML pages live one level up from backend/
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def create_app() -> Flask:
    Config.validate()

    app = Flask(__name__)
    app.config["SECRET_KEY"]            = Config.SECRET_KEY
    app.config["DEBUG"]                 = Config.DEBUG
    app.config["PROPAGATE_EXCEPTIONS"]  = False

    logging.basicConfig(
        level   = logging.DEBUG if Config.DEBUG else logging.INFO,
        format  = "[%(levelname)s] %(message)s",
    )

    # CORS — kept for any external tool or future mobile app that calls the API
    CORS(app,
         origins             = Config.CORS_ORIGINS,
         supports_credentials = True,
         allow_headers       = ["Authorization", "Content-Type"],
         methods             = ["GET", "POST", "PUT", "DELETE", "OPTIONS"])

    # ── Blueprints ─────────────────────────────────────────────────────────────
    from routes.auth              import bp as auth_bp
    from routes.public            import bp as public_bp
    from routes.appointments      import bp as apt_bp
    from routes.doctor_dashboard  import bp as doctor_bp
    from routes.admin_dashboard   import bp as admin_bp
    from routes.packages          import bp as packages_bp

    app.register_blueprint(auth_bp,      url_prefix="/api/auth")
    app.register_blueprint(public_bp,    url_prefix="/api")
    app.register_blueprint(apt_bp,       url_prefix="/api/appointments")
    app.register_blueprint(doctor_bp,    url_prefix="/api/doctor")
    app.register_blueprint(admin_bp,     url_prefix="/api/admin")
    app.register_blueprint(packages_bp,  url_prefix="/api/packages")

    # ── Health check ───────────────────────────────────────────────────────────
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "hospital": "Aadityaa Hospital"})

    # ── Serve the frontend HTML pages ──────────────────────────────────────────
    # All non-/api routes serve static files from the project root directory.
    # Blueprint routes registered above always take priority over these catch-all routes.

    @app.route("/")
    def serve_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def serve_static(filename):
        file_path = os.path.join(FRONTEND_DIR, filename)
        if os.path.isfile(file_path):
            return send_from_directory(FRONTEND_DIR, filename)
        # File not found — return the 404 JSON (don't redirect to index for missing files)
        return jsonify({"error": f"'{filename}' not found."}), 404

    # ── Error handlers — always return JSON ────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request.", "detail": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Authentication required."}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Access denied."}), 403

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.exception("Unhandled error: %s", e)
        detail = str(e) if Config.DEBUG else "Please try again."
        return jsonify({"error": "Server error.", "detail": detail}), 500

    return app


app = create_app()

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  Aadityaa Hospital  →  http://localhost:{Config.PORT}/")
    print(f"  API health check   →  http://localhost:{Config.PORT}/api/health")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
