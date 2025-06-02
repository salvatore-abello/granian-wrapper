from granian_web import App, PlainTextResponse, FileResponse, JSONResponse, parse_qs

app = App(__name__)

async def index(request, proto):
    return PlainTextResponse("Hello, World!")

async def echo(request, proto):
    args = await parse_qs(request.query_string)

    to_response = args.get("echo", "No echo parameter provided")
    return PlainTextResponse(to_response)

async def send_file_test(request, proto):
    return FileResponse("test.txt", 200)

async def serve_file(request, proto, file):
    return PlainTextResponse(f"Serving static file: {file}", 200)

async def get_body(request, proto):
    body = b""
    async for x in proto:
        body += x

    return PlainTextResponse(body)

app.get("/", index)
app.register("/echo", echo)
app.get("/testfile", send_file_test)
app.get("/test/{file}", serve_file)
app.post("/get-body", get_body)
