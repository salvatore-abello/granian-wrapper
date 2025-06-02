import io
import json
from multipart import MultipartParser, parse_options_header
from urllib.parse import parse_qs as urllib_parse_qs

from typing import AsyncGenerator

MAX_BODY = 10 * 1024 * 1024


async def parse_qs(query_string: str) -> AsyncGenerator[dict[str, str | list[str]]]:
    query = urllib_parse_qs(query_string)
    yield {k: v[0] if len(v) == 1 else v for k, v in query.items()}

async def read_all(proto, limit: int = MAX_BODY) -> bytes:
    buf = bytearray()
    async for chunk in proto:
        buf += chunk
        if len(buf) > limit:
            raise ValueError("request body too large")
    return bytes(buf)

async def parse_body(context) -> AsyncGenerator[dict | str | bytes]:
    raw_ct = context.request.headers.get("content-type", "") or "application/octet-stream"
    mime_type, params = parse_options_header(raw_ct)

    if mime_type == "application/json":
        raw_body = await read_all(context.proto)
        charset = params.get("charset", "utf-8")
        yield json.loads(raw_body.decode(charset))

    if mime_type == "application/x-www-form-urlencoded":
        raw_body = await read_all(context.proto)
        charset = params.get("charset", "utf-8")
        yield parse_qs(raw_body.decode(charset))

    if mime_type == "multipart/form-data":
        boundary = params.get("boundary")
        if not boundary:
            raise ValueError("multipart request missing boundary")
        raw_body = await read_all(context.proto) 
        yield parse_multipart(raw_body, boundary.encode())

    yield await read_all(context.proto)


def parse_multipart(body: bytes, boundary: bytes) -> dict[str, str | dict | list]:
    parser = MultipartParser(io.BytesIO(body), boundary)

    temp: dict[str, str | dict | list] = {}

    for part in parser.parts():
        disp, disp_params = parse_options_header(part.headers["Content-Disposition"])
        name = disp_params["name"]

        if "filename" in disp_params or "filename*" in disp_params:
            file_dict = {
                "filename": part.filename,
                "content-type": part.content_type,
                "content": part.raw,
            }
            value: str | dict
            value = file_dict
        else:
            # Text field: decode using UTF-8 (replace errors)
            text = part.raw.decode("utf-8", errors="replace") # TODO: is this ok?
            value = text

        existing = temp.get(name)
        if existing is None:
            temp[name] = value
        else:
            # If this is the second occurrence, wrap the existing value in a list
            if not isinstance(existing, list):
                temp[name] = [existing, value]
            else:
                existing.append(value)

    return temp
