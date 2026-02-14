from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user_id
from app.config import Settings, get_settings
from app.schemas import DocsPageResponse, DocsTreeNode
from app.services.docs import build_docs_tree, read_docs_page

router = APIRouter(prefix="/v1/docs", tags=["docs"])


@router.get("/tree", response_model=list[DocsTreeNode])
async def docs_tree(
    _: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings),
) -> list[DocsTreeNode]:
    return build_docs_tree(Path(settings.docs_root))


@router.get("/page", response_model=DocsPageResponse)
async def docs_page(
    path: str = Query(..., min_length=3),
    _: str = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings),
) -> DocsPageResponse:
    try:
        return read_docs_page(Path(settings.docs_root), path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
