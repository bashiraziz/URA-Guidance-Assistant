from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import DocSectionNode, DocSectionPage, DocsPageResponse, DocsTreeNode
from app.services.docs import build_docs_tree, build_sections_tree, read_docs_page, read_section_page

router = APIRouter(prefix="/v1/docs", tags=["docs"])


@router.get("/tree", response_model=list[DocsTreeNode])
async def docs_tree(
    session: AsyncSession = Depends(get_session),
) -> list[DocsTreeNode]:
    return await build_docs_tree(session)


@router.get("/page", response_model=DocsPageResponse)
async def docs_page(
    path: str = Query(..., min_length=3),
    session: AsyncSession = Depends(get_session),
) -> DocsPageResponse:
    try:
        return await read_docs_page(session, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/sections/tree", response_model=list[DocSectionNode])
async def sections_tree(
    session: AsyncSession = Depends(get_session),
) -> list[DocSectionNode]:
    return await build_sections_tree(session)


@router.get("/sections/page", response_model=DocSectionPage)
async def section_page(
    path: str = Query(..., min_length=1),
    session: AsyncSession = Depends(get_session),
) -> DocSectionPage:
    try:
        return await read_section_page(session, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
