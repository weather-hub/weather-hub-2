import os

from flask import jsonify, render_template

# Optional local fakenodo service - used when FAKENODO_URL is set in the environment
from app.modules.fakenodo.services import FakenodoService
from app.modules.zenodo import zenodo_bp
from app.modules.zenodo.services import ZenodoService


@zenodo_bp.route("/zenodo", methods=["GET"])
def index():
    return render_template("zenodo/index.html")


@zenodo_bp.route("/zenodo/test", methods=["GET"])
def zenodo_test() -> dict:
    """Run a small end-to-end test against Zenodo or Fakenodo depending on configuration.

    If the environment variable `FAKENODO_URL` is set (to any value) the endpoint will use the
    local `FakenodoService` to perform the create/upload/publish/delete flow. This avoids
    making real network calls (and SSL verification issues) during local development.
    """
    # If FAKENODO_URL is set, prefer the local fakenodo service for testing
    if os.getenv("FAKENODO_URL"):
        service = FakenodoService()
        try:
            rec = service.create_deposition(metadata={"title": "fakenodo-test"})
            deposition_id = rec["id"]

            uploaded = service.upload_file(deposition_id, "test.txt", b"hello")
            published = service.publish_deposition(deposition_id)
            service.delete_deposition(deposition_id)

            messages = [
                f"created:{deposition_id}",
                "uploaded" if uploaded else "upload-failed",
                f"published:{published.get('doi') if published else 'no'}",
                "deleted",
            ]
            return jsonify({"success": True, "messages": messages}), 200
        except Exception as exc:
            return jsonify({"success": False, "messages": [str(exc)]}), 500

    # Fallback to real Zenodo API
    service = ZenodoService()
    return service.test_full_connection()
