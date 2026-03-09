from fastapi import FastAPI
from fastapi.middleware import cors
from fastapi.responses import RedirectResponse


# =========================#
#                          #
#   FastAPI Server         #
#                          #
# =========================#

app = FastAPI(
    title="devOS API Server",
    description="API server for devOS to manage DAO specifications and Git repository versions.",
)


app.add_middleware(
    cors.CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
async def read_root():
    return RedirectResponse(url="/docs")



# ===================== #
#                       #
#   RUN API SERVER      #
#                       #
# ===================== #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
