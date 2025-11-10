from flask import jsonify, request

from app.modules.fakenodo import fakenodo_bp
from app.modules.fakenodo.services import FakenodoService

_service = FakenodoService()


@fakenodo_bp.route("/", methods=["GET"])
def test_connection_fakenodo():
    return jsonify({"status": "success", "message": "Connected to FakenodoAPI"})


@fakenodo_bp.route("/deposit/depositions", methods=["POST"])
def create_deposition():
    payload = request.get_json(silent=True) or {}
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    record = _service.create_deposition(metadata=metadata)
    return jsonify(record), 201


@fakenodo_bp.route("/deposit/depositions", methods=["GET"])
def get_all_depositions():
    records = _service.list_depositions()
    return jsonify({"depositions": records}), 200


@fakenodo_bp.route("/deposit/depositions/<int:deposition_id>", methods=["GET"])
def get_deposition(deposition_id):
    rec = _service.get_deposition(deposition_id)
    if not rec:
        return jsonify({"message": "Deposition not found"}), 404
    return jsonify(rec), 200


@fakenodo_bp.route("/deposit/depositions/<depositionId>", methods=["DELETE"])
def delete_deposition_fakenodo(depositionId):
    success = _service.delete_deposition(depositionId)
    if success:
        return jsonify({"status": "success", "message": f"Succesfully deleted deposition {depositionId}"}), 200
    return jsonify({"status": "error", "message": "Not found"}), 404


@fakenodo_bp.route("/deposit/depositions/<int:deposition_id>/files", methods=["POST"])
def upload_file(deposition_id):
    uploaded = request.files.get("file")
    name = request.form.get("name") or (uploaded.filename if uploaded else None)
    content = uploaded.read() if uploaded else None

    if not name:
        return jsonify({"message": "No file name provided"}), 400

    file_record = _service.upload_file(deposition_id, name, content)
    if not file_record:
        return jsonify({"message": "Deposition not found"}), 404
    return jsonify(file_record), 201


@fakenodo_bp.route("/deposit/depositions/<int:deposition_id>/actions/publish", methods=["POST"])
def publish_deposition(deposition_id):
    version = _service.publish_deposition(deposition_id)
    if not version:
        return jsonify({"message": "Deposition not found"}), 404
    return jsonify(version), 202


@fakenodo_bp.route("/deposit/depositions/<int:deposition_id>/nonexistent", methods=["GET"])
def deposition_not_found(deposition_id):
    return jsonify({"message": "Deposition not found"}), 404


@fakenodo_bp.route("/test", methods=["GET"])
def test_endpoint():
    messages = []
    try:
        rec = _service.create_deposition(metadata={"title": "fakenodo-test"})
        messages.append(f"created:{rec['id']}")

        uploaded = _service.upload_file(rec["id"], "test.txt", b"hola")
        if uploaded:
            messages.append("uploaded")

        version = _service.publish_deposition(rec["id"])
        if version:
            messages.append(f"published:{version.get('doi')}")

        _service.delete_deposition(rec["id"])
        messages.append("deleted")

        return jsonify({"success": True, "messages": messages}), 200
    except Exception as exc:
        return jsonify({"success": False, "messages": [str(exc)]}), 500
