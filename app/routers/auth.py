from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.user import User
from ..utils.password import hash_password, verify_password
from ..utils.const import PASSWORD_MAX_LENGTH
from ..services.db.user_quota import create_user_quota

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register")
async def register_page(request: Request):
    """Страница регистрации"""
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error": None}
    )


@router.post("/register")
async def register(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        confirm_password: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    """Обработка регистрации"""

    # Проверка совпадения паролей
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Пароли не совпадают"}
        )

    # Проверка длины пароля (bcrypt ограничение)
    if len(password) > PASSWORD_MAX_LENGTH:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": f"Пароль не должен превышать {PASSWORD_MAX_LENGTH} символа"}
        )

    # Проверка, существует ли пользователь с таким username
    result = await db.execute(select(User).where(User.username == username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Пользователь с таким именем уже существует"}
        )

    # Проверка, существует ли пользователь с таким email
    result = await db.execute(select(User).where(User.email == email))
    existing_email = result.scalar_one_or_none()
    if existing_email:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Пользователь с таким email уже существует"}
        )

    # Создаём нового пользователя
    new_user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password)
    )

    db.add(new_user)
    await db.flush()

    await create_user_quota(db, new_user.id)
    await db.commit()

    # Перенаправляем на страницу входа
    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/login")
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None}
    )


@router.post("/login")
async def login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    """Обработка входа"""

    # Ищем пользователя
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Неверное имя пользователя или пароль"}
        )

    # Сохраняем ID пользователя в сессии
    request.session["user_id"] = user.id
    request.session["username"] = user.username

    # Перенаправляем на дашборд
    return RedirectResponse(url="/projects/", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Выход из системы"""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
