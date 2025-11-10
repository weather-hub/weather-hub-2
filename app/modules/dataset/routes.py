import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional
from zipfile import ZipFile

# from valid_files import valid_files
from flask import abort, jsonify, make_response, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from app.modules.dataset import dataset_bp
from app.modules.dataset.forms import DataSetForm
from app.modules.dataset.models import DSDownloadRecord
from app.modules.dataset.services import (
    AuthorService,
    DataSetService,
    DOIMappingService,
    DSDownloadRecordService,
    DSMetaDataService,
    DSViewRecordService,
)
from app.modules.fakenodo.services import FakenodoService

logger = logging.getLogger(__name__)


dataset_service = DataSetService()
author_service = AuthorService()
dsmetadata_service = DSMetaDataService()


class FakenodoAdapter:
    """Minimal adapter around the in-memory FakenodoService.

    Purpose: expose the small subset of methods the rest of the app expects
    (create_new_deposition, upload_file, publish_deposition, get_doi) while
    keeping file-reading logic local to this adapter.
    """

    def __init__(self, working_dir: str | None = None):
        self.service = FakenodoService(working_dir=working_dir)

    def create_new_deposition(self, dataset) -> dict:
        title = getattr(dataset, "title", f"dataset-{getattr(dataset, 'id', '')}")
        rec = self.service.create_deposition(metadata={"title": title})
        return {"id": rec["id"], "conceptrecid": True, "metadata": rec.get("metadata", {})}

    def _read_feature_model_content(self, feature_model) -> Optional[bytes]:
        """Return file bytes for the given feature_model or None if not available."""
        path = getattr(feature_model, "file_path", None) or getattr(feature_model, "path", None)
        if not path:
            return None
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except Exception:
            return None

    def upload_file(self, dataset, deposition_id, feature_model) -> Optional[dict]:
        name = getattr(feature_model, "filename", None) or getattr(feature_model, "name", None)
        if not name:
            name = f"feature_model_{getattr(feature_model, 'id', uuid.uuid4())}.bin"
        content = self._read_feature_model_content(feature_model)
        return self.service.upload_file(deposition_id, name, content)

    def publish_deposition(self, deposition_id):
        return self.service.publish_deposition(deposition_id)

    def get_doi(self, deposition_id):
        rec = self.service.get_deposition(deposition_id)
        if not rec:
            return None
        doi = rec.get("doi")
        if doi:
            return doi
        versions = rec.get("versions") or []
        return versions[-1].get("doi") if versions else None


zenodo_service = FakenodoAdapter()
doi_mapping_service = DOIMappingService()
ds_view_record_service = DSViewRecordService()


@dataset_bp.route("/dataset/upload", methods=["GET", "POST"])
@login_required
def create_dataset():
    form = DataSetForm()
    if request.method != "POST":
        return render_template("dataset/upload_dataset.html", form=form)

    # POST handler
    if not form.validate_on_submit():
        return jsonify({"message": form.errors}), 400

    dataset = None
    try:
        logger.info("Creating dataset...")
        dataset = dataset_service.create_from_form(form=form, current_user=current_user)
        logger.info(f"Created dataset: {dataset}")

        # Move files from user's temp folder into permanent upload location
        dataset_service.move_feature_models(dataset)

    except ValueError as e:
        logger.info(f"Validation error while creating dataset: {e}")
        return jsonify({"message": str(e)}), 400
    except Exception:
        logger.exception("Exception while creating dataset")
        return jsonify({"message": "Internal server error while creating dataset"}), 500

    # Perform Zenodo/Fakenodo flow (create deposition, upload files, publish, update DOI)
    zenodo_response = _perform_zenodo_flow(dataset)
    if isinstance(zenodo_response, tuple):
        # helper returned a Flask response (e.g. upload/publish error)
        return zenodo_response

    # Cleanup temp folder
    _cleanup_user_temp(current_user)

    return jsonify({"message": "Everything works!"}), 200


def _perform_zenodo_flow(dataset):
    """Create deposition and push feature models to Zenodo (or Fakenodo adapter).

    Returns None on success, or a Flask response (body, status) when a recoverable
    error occurs that the original code returned as 200 with a message.
    """
    data = {}
    try:
        zenodo_response_json = zenodo_service.create_new_deposition(dataset)
        data = json.loads(json.dumps(zenodo_response_json))
    except Exception as exc:
        logger.exception(f"Exception while create dataset data in Zenodo {exc}")
        data = {}

    if not data.get("conceptrecid"):
        return None

    deposition_id = data.get("id")
    dataset_service.update_dsmetadata(dataset.ds_meta_data_id, deposition_id=deposition_id)

    try:
        for feature_model in dataset.feature_models:
            zenodo_service.upload_file(dataset, deposition_id, feature_model)

        zenodo_service.publish_deposition(deposition_id)

        deposition_doi = zenodo_service.get_doi(deposition_id)
        dataset_service.update_dsmetadata(dataset.ds_meta_data_id, dataset_doi=deposition_doi)
    except Exception as e:
        msg = f"it has not been possible upload feature models in Zenodo and update the DOI: {e}"
        return jsonify({"message": msg}), 200

    return None


def _cleanup_user_temp(user):
    file_path = user.temp_folder()
    if os.path.exists(file_path) and os.path.isdir(file_path):
        try:
            shutil.rmtree(file_path)
        except Exception:
            logger.exception(f"Failed to remove temp folder: {file_path}")


@dataset_bp.route("/dataset/list", methods=["GET", "POST"])
@login_required
def list_dataset():
    return render_template(
        "dataset/list_datasets.html",
        datasets=dataset_service.get_synchronized(current_user.id),
        local_datasets=dataset_service.get_unsynchronized(current_user.id),
    )


@dataset_bp.route("/dataset/file/upload", methods=["POST"])
@login_required
def upload():
    file = request.files["file"]
    temp_folder = current_user.temp_folder()
    if not file or not file.filename.endswith(("csv", "txt", "md")):
        return jsonify({"message": "No valid file"}), 400
    # create temp folder
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    file_path = os.path.join(temp_folder, file.filename)

    if os.path.exists(file_path):
        # Generate unique filename (by recursion)
        base_name, extension = os.path.splitext(file.filename)
        i = 1
        while os.path.exists(os.path.join(temp_folder, f"{base_name} ({i}){extension}")):
            i += 1
        new_filename = f"{base_name} ({i}){extension}"
        file_path = os.path.join(temp_folder, new_filename)
    else:
        new_filename = file.filename

    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

    return (
        jsonify(
            {
                "message": "File uploaded and validated successfully",
                "filename": new_filename,
            }
        ),
        200,
    )


@dataset_bp.route("/dataset/file/delete", methods=["POST"])
def delete():
    data = request.get_json()
    filename = data.get("file")
    temp_folder = current_user.temp_folder()
    filepath = os.path.join(temp_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"message": "File deleted successfully"})

    return jsonify({"error": "Error: File not found"})


@dataset_bp.route("/dataset/download/<int:dataset_id>", methods=["GET"])
def download_dataset(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    file_path = f"uploads/user_{dataset.user_id}/dataset_{dataset.id}/"

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"dataset_{dataset_id}.zip")

    with ZipFile(zip_path, "w") as zipf:
        for subdir, dirs, files in os.walk(file_path):
            for file in files:
                full_path = os.path.join(subdir, file)

                relative_path = os.path.relpath(full_path, file_path)

                zipf.write(
                    full_path,
                    arcname=os.path.join(os.path.basename(zip_path[:-4]), relative_path),
                )

    user_cookie = request.cookies.get("download_cookie")
    if not user_cookie:
        # Generate a new unique identifier if it does not exist
        user_cookie = str(uuid.uuid4())
        # Save the cookie to the user's browser
        resp = make_response(
            send_from_directory(
                temp_dir,
                f"dataset_{dataset_id}.zip",
                as_attachment=True,
                mimetype="application/zip",
            )
        )
        resp.set_cookie("download_cookie", user_cookie)
    else:
        resp = send_from_directory(
            temp_dir,
            f"dataset_{dataset_id}.zip",
            as_attachment=True,
            mimetype="application/zip",
        )

    # Check if the download record already exists for this cookie
    existing_record = DSDownloadRecord.query.filter_by(
        user_id=current_user.id if current_user.is_authenticated else None,
        dataset_id=dataset_id,
        download_cookie=user_cookie,
    ).first()

    if not existing_record:
        # Record the download in your database
        DSDownloadRecordService().create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset_id,
            download_date=datetime.now(timezone.utc),
            download_cookie=user_cookie,
        )

    return resp


@dataset_bp.route("/doi/<path:doi>/", methods=["GET"])
def subdomain_index(doi):
    # Check if the DOI is an old DOI
    new_doi = doi_mapping_service.get_new_doi(doi)
    if new_doi:
        # Redirect to the same path with the new DOI
        return redirect(url_for("dataset.subdomain_index", doi=new_doi), code=302)

    # Try to search the dataset by the provided DOI (which should already be the new one)
    ds_meta_data = dsmetadata_service.filter_by_doi(doi)

    if not ds_meta_data:
        abort(404)

    # Get dataset
    dataset = ds_meta_data.data_set

    # Save the cookie to the user's browser
    user_cookie = ds_view_record_service.create_cookie(dataset=dataset)
    resp = make_response(render_template("dataset/view_dataset.html", dataset=dataset))
    resp.set_cookie("view_cookie", user_cookie)

    return resp


@dataset_bp.route("/dataset/unsynchronized/<int:dataset_id>/", methods=["GET"])
@login_required
def get_unsynchronized_dataset(dataset_id):
    # Get dataset
    dataset = dataset_service.get_unsynchronized_dataset(current_user.id, dataset_id)

    if not dataset:
        abort(404)

    return render_template("dataset/view_dataset.html", dataset=dataset)
