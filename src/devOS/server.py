import typing
from fastapi import FastAPI
from fastapi.middleware import cors
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from devOS.use_cases.utils.file_io import File
from devOS.use_cases.manage_git_repo import ManageGitRepositoryUseCase
from devOS.use_cases.read_dao_spec import convert_dao_spec_to_reactflow
from devOS.use_cases.set_dao_spec import build_dao_spec


class ReactFlowRequest(BaseModel):
    nodes: list[dict[str, typing.Any]]
    edges: list[dict[str, typing.Any]]


# =========================#
#                          #
#   Layout Persistence     #
#                          #
# =========================#


def _load_saved_positions() -> dict[str, dict[str, float]]:
    """Load saved node positions from the layout file."""
    layout_file = File("specs", "dao_layout.json")
    if not layout_file.exists():
        return {}
    try:
        data = layout_file.get_json()
        return data.get("positions", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_positions(nodes: list[dict[str, typing.Any]]) -> None:
    """Extract and save node positions to the layout file."""
    positions: dict[str, dict[str, float]] = {}
    for node in nodes:
        node_id = node.get("id")
        position = node.get("position")
        if node_id and position:
            positions[node_id] = {
                "x": float(position.get("x", 0)),
                "y": float(position.get("y", 0)),
            }
    File("specs", "dao_layout.json").write_json({"positions": positions})


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


@app.get("/dao", response_model=ReactFlowRequest)
def get_dao():
    dao_example = File("specs", "dao_spec.json").get_json()
    saved_positions = _load_saved_positions()
    nodes, edges = convert_dao_spec_to_reactflow(
        dao_example,  # type: ignore
        saved_positions=saved_positions,
    )
    return ReactFlowRequest(nodes=nodes, edges=edges)


@app.post("/dao")
def post_dao(request: ReactFlowRequest):
    print("Saving DAO spec and layout positions...")
    _save_positions(request.nodes)
    specs = build_dao_spec(request.nodes, request.edges)  # type: ignore
    File("specs", "dao_spec.json").write_json([spec.model_dump() for spec in specs])
    return dict(status="success", count=len(specs))


@app.get("/version")
def get_version():
    return dict(version=ManageGitRepositoryUseCase().latest_version)


# ===================== #
#                       #
#   RUN API SERVER      #
#                       #
# ===================== #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
