import modal

image = modal.Image.debian_slim().uv_pip_install("fastapi[standard]")
app = modal.App(name="example-basic-web", image=image)


@app.function()
@modal.fastapi_endpoint(
    docs=True  # adds interactive documentation in the browser
)
def hello():
    return "Hello world!"