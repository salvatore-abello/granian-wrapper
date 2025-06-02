from granian_web import App, PlainTextResponse, FileResponse, JSONResponse

app = App(__name__, debug=True)

async def index(context):
    return PlainTextResponse("Hello, World!")

async def echo(context):
    args = await context.args

    to_response = args.get("echo", "No echo parameter provided")
    return PlainTextResponse(to_response)

async def send_file_test(context):
    return FileResponse("test.txt", 200)

async def serve_file(context, file):
    return PlainTextResponse(f"Serving static file: {file}", 200)

async def get_body(context):
    body = await context.body
    return JSONResponse(f"{body}")

app.get("/", index)
app.register("/echo", echo)
app.get("/testfile", send_file_test)
app.get("/test/{file}", serve_file)
app.post("/get-body", get_body)
