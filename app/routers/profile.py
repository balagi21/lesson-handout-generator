from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.db.user_quota import get_user_quota
from ..database import get_db

router = APIRouter(prefix="/profile", tags=["profile"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def get_profile(
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    quota = await get_user_quota(db, user_id)
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            'quota': quota
        }
    )
