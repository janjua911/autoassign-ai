"""
utils/drive.py
Google Drive upload and link sharing via Service Account.
"""

from pathlib import Path
from loguru import logger
from core.config import cfg


class DriveUploader:
    """
    Uploads files to Google Drive and returns shareable links.
    Requires a Service Account JSON from Google Cloud Console.

    Setup:
        1. Google Cloud Console → New Project
        2. Enable Google Drive API
        3. IAM → Service Account → Create → Download JSON
        4. Save JSON path in user_config.yaml
        5. Share target folder with service account email

    Usage:
        from utils.drive import drive
        link = drive.upload("outputs/assignment.pdf", "Assignment1.pdf")
    """

    def __init__(self):
        self._service = None
        self._folder_id = None

    def _get_service(self):
        if self._service:
            return self._service
        if not cfg.drive_enabled:
            raise RuntimeError("Google Drive is disabled in config")
        sa_path = cfg.drive_service_account
        if not Path(sa_path).exists():
            raise FileNotFoundError(
                f"Service account JSON not found: {sa_path}\n"
                "Follow setup instructions in utils/drive.py"
            )
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
        self._service = build("drive", "v3", credentials=creds)
        logger.info("Google Drive service initialized")
        return self._service

    def _get_or_create_folder(self) -> str:
        """Get the AutoAssign folder ID, creating it if needed."""
        if self._folder_id:
            return self._folder_id
        service = self._get_service()
        folder_name = cfg.drive_folder
        # Search for existing folder
        results = service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        if files:
            self._folder_id = files[0]["id"]
            logger.info(f"Using existing Drive folder: {folder_name}")
        else:
            # Create new folder
            meta = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = service.files().create(body=meta, fields="id").execute()
            self._folder_id = folder["id"]
            logger.info(f"Created Drive folder: {folder_name}")
        return self._folder_id

    def upload(self, file_path: str, filename: str = None) -> str:
        """
        Upload a file to Google Drive and return a shareable link.
        Returns: shareable URL string, or "" on failure.
        """
        from googleapiclient.http import MediaFileUpload
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return ""
        try:
            service = self._get_service()
            folder_id = self._get_or_create_folder()
            display_name = filename or path.name
            # Detect MIME type
            mime = "application/pdf" if path.suffix == ".pdf" else "application/octet-stream"
            file_meta = {"name": display_name, "parents": [folder_id]}
            media = MediaFileUpload(str(path), mimetype=mime, resumable=True)
            uploaded = service.files().create(
                body=file_meta, media_body=media, fields="id"
            ).execute()
            file_id = uploaded["id"]
            # Make it shareable (anyone with link can view)
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()
            link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            logger.info(f"Uploaded to Drive: {display_name} → {link}")
            return link
        except Exception as e:
            logger.error(f"Drive upload failed: {e}")
            return ""

    def delete(self, file_id: str) -> bool:
        """Delete a file from Drive by ID."""
        try:
            self._get_service().files().delete(fileId=file_id).execute()
            logger.info(f"Deleted Drive file: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Drive delete failed: {e}")
            return False


drive = DriveUploader()
