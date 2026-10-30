"""Supabase login check for API routes.

Reads SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY and SUPABASE_DISABLED from the
app config (set in app.py). The signed-in user is stored in `g.auth_user`.
"""

from functools import wraps

import requests
from flask import current_app, g, jsonify, request

# Stand-in user while DISABLE_SUPABASE=true.
DEV_USER = {"id": "00000000-0000-0000-0000-000000000000", "email": "dev@localhost"}


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        config = current_app.config
        if config.get("SUPABASE_DISABLED"):
            g.auth_user = DEV_USER
            return view(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        scheme, separator, token = auth_header.partition(" ")

        if scheme.lower() != "bearer" or not separator or not token:
            return jsonify({"error": "Please log in first"}), 401

        try:
            response = requests.get(
                f"{config['SUPABASE_URL'].rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": config["SUPABASE_PUBLISHABLE_KEY"],
                    "Authorization": f"Bearer {token}",
                },
                timeout=10,
            )
        except requests.RequestException:
            current_app.logger.exception("Could not contact Supabase Auth")
            return jsonify({"error": "Could not verify login"}), 503

        if response.status_code in (401, 403):
            return jsonify({"error": "Login is invalid or expired"}), 401

        if not response.ok:
            current_app.logger.error(
                "Supabase Auth returned HTTP %s", response.status_code
            )
            return jsonify({"error": "Could not verify login"}), 503

        try:
            g.auth_user = response.json()
        except ValueError:
            return jsonify({"error": "Could not verify login"}), 503

        return view(*args, **kwargs)

    return wrapped
