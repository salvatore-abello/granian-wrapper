import re
import logging
import traceback
from typing import Callable, Dict, List, Optional, Tuple, Any

from .responses import Response, PlainTextResponse, FileResponse, StreamResponse
from .util import parse_body, parse_qs


class Context:
    def __init__(self, request, proto):
        self.request = request
        self.proto = proto
        self._body = None
        self._args = None
    
    @property
    async def body(self):
        if self._body is None:
            self._body = await anext(parse_body(self))
        return self._body
    
    @property
    async def args(self):
        if self._args is None:
            self._args = await anext(parse_qs(self))
        return self._args

    def __aiter__(self):
        return self.proto.__aiter__()
    
    async def __anext__(self):
        return await self.proto.__anext__()


class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)

__version__ = "1.0.0"
__all__ = ["App", "Context"]


class App:
    def __init__(self, name: str, enable_logging: bool = True, debug: bool = False):
        self.name: str = name
        self.debug: bool = debug
        self._static: Dict[Tuple[str, str], Callable] = {}
        self._parametric: List[Tuple[re.Pattern, str, Callable]] = []
        self._fallback: Optional[Tuple[str, Callable]] = None
        
        self.logger = logging.getLogger(self.name)
        if enable_logging and not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = ColoredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        elif not enable_logging:
            self.logger.setLevel(logging.CRITICAL)

    def _log(self, message: str, level: str = "INFO") -> None:
        getattr(self.logger, level.lower())(message)

    def _debug(self, message: str) -> None:
        self.logger.debug(message)

    def register(self, path: str, func: Callable, method: str = "GET") -> None:
        if not callable(func):
            raise TypeError(f"Handler for path '{path}' must be callable.")

        method = method.upper()
        self._log(f"Registering route: {method} {path}", "DEBUG")

        if path == "*":
            self._fallback = (method, func)
            self._log(f"Registered fallback handler for method: {method}", "DEBUG")
            return

        if "{" not in path:
            key = (path, method)
            if key in self._static:
                raise ValueError(f"Path '{path}' with method '{method}' is already registered.")
            self._static[key] = func
            self._log(f"Registered static route: {method} {path}", "DEBUG")
            return

        regex = self._compile_parametric(path)
        self._parametric.append((regex, method, func))
        self._log(f"Registered parametric route: {method} {path} -> {regex.pattern}", "DEBUG")

    async def handler(self, scope, proto):
        # static routes -> parametric routes -> fallback

        path: str = scope.path
        method: str = scope.method.upper()
        context = Context(scope, proto)

        try:
            func = self._static.get((path, method))
            if func is not None:
                response = await func(context)
                return response

            for regex, mth, fn in self._parametric:
                if mth != method:
                    continue

                match = regex.match(path)
                if match is not None:
                    response = await fn(context, **match.groupdict())
                    return response

            if self._fallback and (self._fallback[0] == method or self._fallback[0] == "*"):
                response = await self._fallback[1](context)
                return response

            return PlainTextResponse("Not Found", 404)

        except Exception as exc:
            self._log(f"Error in handler for {method} {path}: {exc}", "ERROR")
            self._log(traceback.format_exc(), "DEBUG")
            return PlainTextResponse("Internal Server Error", 500)

    async def __call__(self, scope, proto):
        path: str = scope.path
        method: str = scope.method.upper()
        status_code = 500
        
        try:
            response = await self.handler(scope, proto)
            status_code = response.status_code

            if isinstance(response, FileResponse):
                proto.response_file(
                    status=response.status_code,
                    headers=[
                        ("content-type", "application/octet-stream"),
                        (
                            "content-disposition",
                            f"attachment; filename=\"{response.file_path.split('/')[-1]}\"",
                        ),
                    ],
                    file=response.file_path,
                )
                self._log(f"{method} {path} - {status_code}")
                return

            if isinstance(response, StreamResponse):
                try:
                    transport = proto.response_stream(
                        status=response.status_code,
                        headers=[("content-type", response.content_type)],
                    )
                    async for chunk in response.body:
                        if isinstance(chunk, str):
                            await transport.send_str(chunk)
                        else:
                            await transport.send_bytes(chunk)

                except Exception as proto_error:
                    self._log(f"Protocol error: {proto_error}", "ERROR")
                    self._log(traceback.format_exc(), "DEBUG")
                    status_code = 500
                self._log(f"{method} {path} - {status_code}")
                return

            if isinstance(response, Response):
                try:
                    if isinstance(response.message, bytes):
                        proto.response_bytes(
                            status=response.status_code,
                            headers=[
                                (
                                    "content-type",
                                    response.to_dict().get("content_type", "application/octet-stream"),
                                )
                            ],
                            body=response.message,
                        )
                    else:
                        proto.response_str(
                            status=response.status_code,
                            headers=[
                                (
                                    "content-type",
                                    response.to_dict().get("content_type", "text/plain"),
                                )
                            ],
                            body=response.message,
                        )
                except Exception as proto_error:
                    self._log(f"Protocol error: {proto_error}", "ERROR")
                    self._log(traceback.format_exc(), "DEBUG")
                    status_code = 500

            self._log(f"{method} {path} - {status_code}")

        except Exception as exc:
            self._log(f"Error while processing the request: {exc}", "ERROR")
            self._log(traceback.format_exc(), "DEBUG")
            try:
                proto.response_str(
                    status=500,
                    headers=[("content-type", "text/plain")],
                    body="Internal Server Error",
                )
            except Exception:
                pass
            self._log(f"{method} {path} - 500")

    @staticmethod
    def _compile_parametric(path: str) -> re.Pattern:
        tokens = []
        for segment in path.strip("/").split("/"):
            if segment.startswith("{") and segment.endswith("}"):
                name = segment[1:-1]
                tokens.append(fr"(?P<{name}>[^/]+)")
            else:
                tokens.append(re.escape(segment))
        pattern = "^/" + "/".join(tokens) + "$"
        return re.compile(pattern)

    def get(self, path: str, func: Callable) -> None:
        self.register(path, func, "GET")

    def post(self, path: str, func: Callable) -> None:
        self.register(path, func, "POST")

    def put(self, path: str, func: Callable) -> None:
        self.register(path, func, "PUT")

    def delete(self, path: str, func: Callable) -> None:
        self.register(path, func, "DELETE")

    def patch(self, path: str, func: Callable) -> None:
        self.register(path, func, "PATCH")
