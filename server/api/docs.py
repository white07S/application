import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from server import settings

router = APIRouter(prefix="/docs", tags=["docs"])

DOCS_CONTENT_DIR = Path(settings.DOCS_CONTENT_DIR)


@router.get("/routes")
async def get_docs_routes():
    """Serve navigation structure."""
    routes_file = DOCS_CONTENT_DIR / "docs_routes.json"
    if not routes_file.exists():
        raise HTTPException(status_code=404, detail="Documentation routes not found. Run indexer first.")
    with open(routes_file) as f:
        return JSONResponse(json.load(f))


@router.get("/search-index")
async def get_search_index():
    """Serve FlexSearch index."""
    index_file = DOCS_CONTENT_DIR / "search_index.json"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Search index not found. Run indexer first.")
    with open(index_file) as f:
        return JSONResponse(json.load(f))


@router.get("/content/{path:path}")
async def get_doc_content(path: str):
    """Serve raw MDX content."""
    if ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    for ext in [".md", ".mdx", ""]:
        file_path = DOCS_CONTENT_DIR / f"{path}{ext}"
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path, media_type="text/markdown")

    raise HTTPException(status_code=404, detail=f"Document not found: {path}")
