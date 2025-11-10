from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from core.services.BaseService import BaseService

DB_FILENAME = "fakenodo_db.json"


def _current_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class FakenodoService(BaseService):
    def __init__(self, working_dir: Optional[str] = None):

        super().__init__(None)
        self.working_dir = working_dir or os.getenv("WORKING_DIR", ".")
        self.db_path = os.path.join(self.working_dir, DB_FILENAME)
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as fh:
                    self._db: Dict = json.load(fh)
            except Exception:
                self._db = {"records": {}, "next_id": 1}
        else:
            self._db = {"records": {}, "next_id": 1}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with open(self.db_path, "w") as fh:
            json.dump(self._db, fh, indent=2, default=str)

    def _next_id(self) -> int:
        nid = self._db.get("next_id", 1)
        self._db["next_id"] = nid + 1
        return nid

    def create_deposition(self, metadata: Optional[Dict] = None) -> Dict:
        with self._lock:
            rid = self._next_id()
            record = {
                "id": rid,
                "metadata": metadata or {},
                "files": [],
                "versions": [],
                "published": False,
                "dirty": False,
                "created_at": _current_iso(),
                "updated_at": _current_iso(),
            }
            self._db.setdefault("records", {})[str(rid)] = record
            self._save()
            return record

    def list_depositions(self) -> List[Dict]:
        with self._lock:
            return list(self._db.get("records", {}).values())

    def get_deposition(self, deposition_id: int) -> Optional[Dict]:
        with self._lock:
            return self._db.get("records", {}).get(str(deposition_id))

    def delete_deposition(self, deposition_id: int) -> bool:
        with self._lock:
            key = str(deposition_id)
            if key in self._db.get("records", {}):
                del self._db["records"][key]
                self._save()
                return True
            return False

    def upload_file(self, deposition_id: int, filename: str, content_bytes: Optional[bytes] = None) -> Optional[Dict]:
        with self._lock:
            rec = self._db.get("records", {}).get(str(deposition_id))
            if not rec:
                return None
            file_rec = {
                "id": str(uuid4()),
                "name": filename,
                "size": len(content_bytes) if content_bytes is not None else 0,
                "created_at": _current_iso(),
            }
            rec["files"].append(file_rec)
            rec["dirty"] = True
            rec["updated_at"] = _current_iso()
            self._save()
            return file_rec

    def publish_deposition(self, deposition_id: int) -> Optional[Dict]:
        with self._lock:
            rec = self._db.get("records", {}).get(str(deposition_id))
            if not rec:
                return None
            last_version = rec["versions"][-1] if rec["versions"] else None
            need_new = last_version is None or rec.get("dirty")
            if not need_new:
                return last_version

            new_version = (last_version.get("version", 0) + 1) if last_version else 1
            doi = f"10.1234/fakenodo.{deposition_id}.v{new_version}"
            version = {
                "version": new_version,
                "doi": doi,
                "metadata": rec.get("metadata"),
                "files": rec.get("files", []).copy(),
                "created_at": _current_iso(),
            }
            rec["versions"].append(version)
            rec["published"] = True
            rec["dirty"] = False
            rec["doi"] = doi
            rec["updated_at"] = _current_iso()
            self._save()
            return version

    def list_versions(self, deposition_id: int) -> Optional[List[Dict]]:
        with self._lock:
            rec = self._db.get("records", {}).get(str(deposition_id))
            if not rec:
                return None
            return rec.get("versions", [])
