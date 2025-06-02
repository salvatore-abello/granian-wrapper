import json
from typing import Union, AsyncIterator


class Response:
    def __init__(self, status_code: int, message: str | bytes):
        self.status_code = status_code
        self.message = message

    def to_dict(self):
        return {
            "status_code": self.status_code,
            "message": self.message
        }

    def __str__(self):
        return f"Response(status_code={self.status_code}, message='{self.message}')"

class StreamResponse(Response):
    def __init__(
        self,
        body: AsyncIterator[Union[bytes, str]],
        *,
        status_code: int = 200,
        content_type: str = "application/octet-stream",
    ):
        super().__init__(status_code, "")
        self.body = body
        self.content_type = content_type

    def to_dict(self):
        return {
            "status_code": self.status_code,
            "message": self.message,
            "content_type": self.content_type,
            "stream": True,
        }

class PlainTextResponse(Response):
    def __init__(self, message: str | bytes, status_code: int = 200):
        super().__init__(status_code, message)

    def to_dict(self):
        return {
            "status_code": self.status_code,
            "message": self.message,
            "content_type": "text/plain"
        }

class JSONResponse(Response):
    def __init__(self, data: dict, status_code: int = 200):
        super().__init__(status_code, json.dumps(data))
        self.data = data

    def to_dict(self):
        return {
            "status_code": self.status_code,
            "message": self.message,
            "content_type": "application/json"
        }

class HTMLResponse(Response):
    def __init__(self, html_content: str | bytes, status_code: int = 200):
        super().__init__(status_code, "OK")
        self.html_content = html_content

    def to_dict(self):
        return {
            "status_code": self.status_code,
            "message": self.message,
            "html_content": self.html_content,
            "content_type": "text/html"
        }

class FileResponse(Response):
    def __init__(self, file_path: str, status_code: int = 200):
        super().__init__(status_code, "OK")
        self.file_path = file_path

    def to_dict(self):
        return {
            "status_code": self.status_code,
            "message": self.message,
            "file_path": self.file_path,
            "content_type": "application/octet-stream"
        }

