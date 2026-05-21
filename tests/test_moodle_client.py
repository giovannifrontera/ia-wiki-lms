import pytest
from unittest.mock import patch, MagicMock
from app.core.moodle_client import MoodleClient, MoodleFile

MOCK_COURSE_CONTENTS = [
    {
        "id": 1,
        "name": "Lezione 1",
        "modules": [
            {
                "id": 10,
                "name": "Slide SO - Scheduling",
                "contents": [
                    {
                        "type": "file",
                        "filename": "scheduling.pdf",
                        "fileurl": "https://moodle.edu/pluginfile.php/1/scheduling.pdf",
                        "filesize": 102400,
                        "mimetype": "application/pdf",
                        "timemodified": 1700000000,
                    }
                ],
            },
            {
                "id": 11,
                "name": "Video introduttivo",
                "contents": [
                    {
                        "type": "file",
                        "filename": "intro.mp4",
                        "fileurl": "https://moodle.edu/pluginfile.php/1/intro.mp4",
                        "filesize": 5000000,
                        "mimetype": "video/mp4",
                        "timemodified": 1700000001,
                    }
                ],
            },
        ],
    }
]

def make_client():
    return MoodleClient(base_url="https://moodle.edu", token="fake-token")

def test_list_course_files_returns_only_pdf_pptx():
    client = make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_COURSE_CONTENTS
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response):
        files = client.list_course_files("101")

    assert len(files) == 1
    assert files[0].filename == "scheduling.pdf"
    assert files[0].mimetype == "application/pdf"

def test_list_course_files_includes_pptx():
    client = make_client()
    pptx_content = [{
        "id": 2, "name": "S2",
        "modules": [{
            "id": 20, "name": "Slide PPTX",
            "contents": [{
                "type": "file",
                "filename": "deadlock.pptx",
                "fileurl": "https://moodle.edu/pluginfile.php/2/deadlock.pptx",
                "filesize": 51200,
                "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "timemodified": 1700000002,
            }],
        }],
    }]
    mock_response = MagicMock()
    mock_response.json.return_value = pptx_content
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response):
        files = client.list_course_files("102")

    assert len(files) == 1
    assert files[0].filename == "deadlock.pptx"

def test_download_file_appends_token():
    client = make_client()
    mock_response = MagicMock()
    mock_response.content = b"%PDF-1.4 fake content"
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response) as mock_get:
        data = client.download_file("https://moodle.edu/pluginfile.php/1/file.pdf")

    assert data == b"%PDF-1.4 fake content"
    called_url = mock_get.call_args[0][0]
    assert "fake-token" in called_url

def test_moodle_api_error_raises():
    client = make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = {"exception": "...", "message": "Invalid token"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client._session, "get", return_value=mock_response):
        with pytest.raises(ValueError, match="Invalid token"):
            client.list_course_files("999")
