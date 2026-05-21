import requests
from dataclasses import dataclass
from typing import List

_SUPPORTED_MIMETYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

@dataclass
class MoodleFile:
    filename: str
    fileurl: str
    filesize: int
    mimetype: str
    timemodified: int

class MoodleClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._session = requests.Session()

    def _call(self, function: str, **params) -> object:
        response = self._session.get(
            f"{self.base_url}/webservice/rest/server.php",
            params={
                "wstoken": self.token,
                "moodlewsrestformat": "json",
                "wsfunction": function,
                **params,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "exception" in data:
            raise ValueError(data.get("message", "Moodle API error"))
        return data

    def list_course_files(self, course_id: str) -> List[MoodleFile]:
        contents = self._call("core_course_get_contents", courseid=course_id)
        files = []
        for section in contents:
            for module in section.get("modules", []):
                for content in module.get("contents", []):
                    if content.get("type") == "file" and content.get("mimetype") in _SUPPORTED_MIMETYPES:
                        files.append(MoodleFile(
                            filename=content["filename"],
                            fileurl=content["fileurl"],
                            filesize=content.get("filesize", 0),
                            mimetype=content["mimetype"],
                            timemodified=content.get("timemodified", 0),
                        ))
        return files

    def download_file(self, fileurl: str) -> bytes:
        url = f"{fileurl}?token={self.token}"
        response = self._session.get(url, timeout=60)
        response.raise_for_status()
        return response.content
