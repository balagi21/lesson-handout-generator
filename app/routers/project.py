import re
import markdown
from fastapi import APIRouter, Request, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete, update
from pydantic import BaseModel
from typing import List
from datetime import datetime, UTC

from ..services.llm import llm_gigachat
from ..services.db.user_quota import consume_quota
from ..services.file_parser import extract_text
from ..database import get_db
from ..models.project import Project, ProjectStatus
from ..models.handout import Handout
from ..models.export import ExportedFile


router = APIRouter(prefix="/projects", tags=["projects"])
templates = Jinja2Templates(directory="app/templates")


class ReorderRequest(BaseModel):
    handout_id: int
    new_order: int


async def get_project_with_validation(db, user_id, project_id):
    """Получает модель проекта по id
    Делает валидацию: есть авторизованный пользователь, и проект принадлежит ему"""
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project



@router.get("/")
async def list_projects(
        request: Request,
        db: AsyncSession = Depends(get_db),
        page: int = 1,
        limit: int = 10
):
    """Список уроков пользователя"""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    offset = (page - 1) * limit

    # Запрос уроков с пагинацией
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(desc(Project.updated_at))
        .offset(offset)
        .limit(limit + 1)  # +1 чтобы понять, есть ли следующая страница
    )
    projects = result.scalars().all()

    has_next = len(projects) > limit
    if has_next:
        projects = projects[:-1]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "projects": projects,
            "page": page,
            "has_next": has_next,
            "has_prev": page > 1
        }
    )


@router.post("/create")
async def create_project(
        request: Request,
        name: str = Form(),
        db: AsyncSession = Depends(get_db)
):
    """Создание нового урока"""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "Unauthorized"}, 401

    new_project = Project(
        user_id=user_id,
        name=name
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)

    return RedirectResponse(url=f"/projects/{new_project.id}/edit", status_code=303)


@router.get("/{project_id}/edit")
async def edit_project(
        request: Request,
        project_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Страница редактирования проекта"""
    user_id = request.session.get("user_id")
    project = await get_project_with_validation(db, user_id, project_id)

    # Проверяем, есть ли этапы у проекта
    handouts_result = await db.execute(
        select(Handout).where(Handout.project_id == project_id)
    )
    handouts = handouts_result.scalars().all()
    all_handouts_generated = all(h.status == 'ready' for h in handouts)
    has_pdf = False
    if all_handouts_generated:
        db_result = await db.execute(
            select(ExportedFile).where(ExportedFile.project_id == project_id)
        )
        has_pdf = db_result.scalar_one_or_none() is not None

    # Получаем метаданные для шага 2 (если есть)
    subject = ""
    grade = ""
    topic = ""
    if project.context_json:
        subject = project.context_json.get("subject", "")
        grade = project.context_json.get("grade", "")
        topic = project.context_json.get("topic", "")

    fill_rendered_content(handouts)

    return templates.TemplateResponse(
        request=request,
        name="project_edit.html",
        context={
            "project": project,
            "subject": subject,
            "grade": grade,
            "topic": topic,
            "handouts": handouts,
            "all_handouts_generated": all_handouts_generated,
            "has_pdf": has_pdf,
        }
    )


def fill_rendered_content(handouts):
    for handout in handouts:
        if handout.content:
            handout.rendered_content = markdown.markdown(
                handout.content,
                extensions=['tables', 'fenced_code']
            )
        else:
            handout.rendered_content = ""


@router.post("/{project_id}/delete")
async def delete_project(
        project_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Удаление проекта"""
    user_id = request.session.get("user_id")
    project = await get_project_with_validation(db, user_id, project_id)

    await db.delete(project)
    await db.commit()

    return RedirectResponse(url="/projects/", status_code=303)


@router.post("/{project_id}/generate-plan")
async def generate_plan(
        project_id: int,
        request: Request,
        prompt: str = Form(None),
        file: UploadFile = File(None),
        db: AsyncSession = Depends(get_db)
):
    if not prompt and not file:
        raise HTTPException(
            status_code=400,
            detail="Укажите описание урока или загрузите файл с планом"
        )
    user_id = request.session.get("user_id")
    project = await get_project_with_validation(db, user_id, project_id)

    if file:
        file_content = await extract_text(file)
    else:
        file_content = ""

    has_quota = await consume_quota(db, user_id, 1)
    if not has_quota:
        raise HTTPException(429, "Превышен дневной лимит запросов")

    llm_result = llm_gigachat.generate_plan(prompt, file_content)

    # Сохраняем метаданные в context_json проекта
    context = project.context_json or {}
    context["subject"] = llm_result.subject
    context["grade"] = llm_result.grade
    context["topic"] = llm_result.topic
    context["generated_from"] = "prompt"
    project.context_json = context
    project.status = ProjectStatus.HANDOUT_GENERATION
    await db.commit()

    # Удаляем существующие этапы
    await db.execute(
        delete(Handout).where(Handout.project_id == project_id)
    )

    # Сохраняем новые этапы
    for idx, stage in enumerate(llm_result.stages):
        handout = Handout(
            project_id=project_id,
            stage_order=idx,
            stage_name=stage.name,
            stage_description=stage.description,
            status="pending"
        )
        db.add(handout)

    await db.commit()

    return await get_project_edit_content_html(project_id, user_id, db, request)


@router.post("/{project_id}/handouts/reorder")
async def reorder_handouts(
        project_id: int,
        request: Request,
        orders: List[ReorderRequest],
        db: AsyncSession = Depends(get_db)
):
    """Изменение порядка этапов"""
    user_id = request.session.get("user_id")
    await get_project_with_validation(db, user_id, project_id)

    # Обновляем порядок
    for order_data in orders:
        await db.execute(
            update(Handout)
            .where(Handout.id == order_data.handout_id, Handout.project_id == project_id)
            .values(stage_order=order_data.new_order)
        )

    await db.commit()

    # Возвращаем обновлённый список этапов
    return await get_stage_list_html(project_id, user_id, db, request)


@router.post("/{project_id}/handouts/{handout_id}/update")
async def update_handout(
        project_id: int,
        handout_id: int,
        request: Request,
        name: str = Form(...),
        description: str = Form(None),
        db: AsyncSession = Depends(get_db)
):
    """Обновление этапа (имя, описание, тип)"""
    user_id = request.session.get("user_id")
    project_info = await get_project_with_validation(db, user_id, project_id)

    result = await db.execute(
        select(Handout).where(Handout.id == handout_id, Handout.project_id == project_id)
    )
    handout = result.scalar_one_or_none()
    if not handout:
        raise HTTPException(status_code=404, detail="Handout not found")

    handout.stage_name = name
    handout.stage_description = description
    handout.updated_at = datetime.now(UTC)

    await db.commit()

    return templates.TemplateResponse(
        request=request,
        name="_stage.html",
        context={
            "handout": handout,
            "project": project_info,
        }
    )


@router.post("/{project_id}/handouts/delete")
async def delete_handout(
        project_id: int,
        request: Request,
        handout_id: int = Form(...),
        db: AsyncSession = Depends(get_db)
):
    """Удаление этапа"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(Handout).where(Handout.id == handout_id, Handout.project_id == project_id)
    )
    handout = result.scalar_one_or_none()
    if handout:
        await db.delete(handout)
        await db.commit()

    # Возвращаем обновлённый список
    return await get_project_edit_content_html(project_id, user_id, db, request)


@router.post("/{project_id}/handouts/create")
async def create_handout(
        project_id: int,
        request: Request,
        name: str = Form(...),
        description: str = Form(""),
        db: AsyncSession = Depends(get_db)
):
    """Создание нового этапа"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Получаем максимальный порядковый номер
    result = await db.execute(
        select(Handout).where(Handout.project_id == project_id)
    )
    existing = result.scalars().all()
    max_order = max([h.stage_order for h in existing], default=-1) + 1

    new_handout = Handout(
        project_id=project_id,
        stage_order=max_order,
        stage_name=name,
        stage_description=description,
        status="pending"
    )
    db.add(new_handout)
    await db.commit()
    await db.refresh(new_handout)

    return await get_stage_list_html(project_id, user_id, db, request)


async def check_all_handouts_generated(project_id: int, db: AsyncSession) -> bool:
    """Проверяет, все ли раздатки проекта сгенерированы"""
    result = await db.execute(
        select(Handout).where(Handout.project_id == project_id)
    )
    handouts = result.scalars().all()

    if not handouts:
        return False

    return all(h.status == "ready" and h.content for h in handouts)


@router.post("/{project_id}/handouts/{handout_id}/generate")
async def generate_handout_content(
        project_id: int,
        handout_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Генерация контента для этапа"""
    user_id = request.session.get("user_id")
    project_info = await get_project_with_validation(db, user_id, project_id)

    db_result = await db.execute(
        select(Handout).where(Handout.id == handout_id, Handout.project_id == project_id)
    )
    handout = db_result.scalar_one_or_none()
    if not handout:
        raise HTTPException(status_code=404, detail="Handout not found")

    has_quota = await consume_quota(db, user_id, 1)
    if not has_quota:
        raise HTTPException(429, "Превышен дневной лимит запросов")

    # Обновляем статус
    handout.status = "generating"
    await db.commit()

    llm_response = llm_gigachat.generate_handout(
        subject=project_info.context_json["subject"],
        grade=project_info.context_json["grade"],
        topic=project_info.context_json["topic"],
        description=handout.stage_description
    )

    handout.content = llm_response.content
    handout.status = "ready"
    handout.generated_at = datetime.now(UTC)
    await db.commit()

    all_generated = await check_all_handouts_generated(project_id, db)

    fill_rendered_content([handout])

    response = templates.TemplateResponse(
        request=request,
        name="_stage.html",
        context={
            "handout": handout,
            "project": project_info,
        }
    )
    if all_generated:
        response.headers["HX-Trigger"] = "all-handouts-generated"
    return response


@router.post("/{project_id}/handouts/generate-all")
async def generate_all_handout_content(
        project_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Генерация контента для эвсех этапов, по которым ещё не было генерации"""
    user_id = request.session.get("user_id")
    project_info = await get_project_with_validation(db, user_id, project_id)

    db_result = await db.execute(
        select(Handout).where(Handout.status == 'pending', Handout.project_id == project_id)
    )
    handouts = db_result.scalars().all()
    if not handouts:
        raise HTTPException(status_code=404, detail="Handouts not found")

    has_quota = await consume_quota(db, user_id, len(handouts))
    if not has_quota:
        raise HTTPException(429, "Превышен дневной лимит запросов")

    # Обновляем статус
    for handout in handouts:
        handout.status = "generating"
    await db.commit()

    for handout in handouts:
        llm_response = llm_gigachat.generate_handout(
            subject=project_info.context_json["subject"],
            grade=project_info.context_json["grade"],
            topic=project_info.context_json["topic"],
            description=handout.stage_description
        )

        handout.content = llm_response.content
        handout.status = "ready"
        handout.generated_at = datetime.now(UTC)
    await db.commit()

    all_generated = await check_all_handouts_generated(project_id, db)

    fill_rendered_content(handouts)

    response = templates.TemplateResponse(
        request=request,
        name="_project_edit_content.html",
        context={
            "project": project_info,
            "handouts": handouts,
            "subject": project_info.context_json.get("subject", "") if project_info and project_info.context_json else "",
            "grade": project_info.context_json.get("grade", "") if project_info and project_info.context_json else "",
            "topic": project_info.context_json.get("topic", "") if project_info and project_info.context_json else "",
            "all_handouts_generated": all_generated,
        }
    )
    if all_generated:
        response.headers["HX-Trigger"] = "all-handouts-generated"
    return response


@router.get("/{project_id}/handouts/{handout_id}/content")
async def get_handout_content(
        project_id: int,
        handout_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Получение контента для редактирования"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(Handout).where(Handout.id == handout_id, Handout.project_id == project_id)
    )
    handout = result.scalar_one_or_none()
    if not handout:
        raise HTTPException(status_code=404, detail="Handout not found")

    return {"content": handout.content or ""}


async def get_project_edit_content_html(project_id: int,
                                        user_id: int,
                                        db: AsyncSession,
                                        request: Request):
    """Вспомогательная функция: возвращает HTML-фрагмент содержимого страницы редактирования проекта"""
    result = await db.execute(
        select(Handout)
        .where(Handout.project_id == project_id)
        .order_by(Handout.stage_order)
    )
    handouts = result.scalars().all()
    fill_rendered_content(handouts)

    # Получаем метаданные проекта
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="_project_edit_content.html",
        context={
            "project": project,
            "handouts": handouts,
            "subject": project.context_json.get("subject", "") if project and project.context_json else "",
            "grade": project.context_json.get("grade", "") if project and project.context_json else "",
            "topic": project.context_json.get("topic", "") if project and project.context_json else ""
        }
    )


async def get_stage_list_html(project_id: int, user_id: int, db: AsyncSession, request: Request):
    """Вспомогательная функция: возвращает HTML-фрагмент со списком этапов"""
    result = await db.execute(
        select(Handout)
        .where(Handout.project_id == project_id)
        .order_by(Handout.stage_order)
    )
    handouts = result.scalars().all()

    # Получаем метаданные проекта
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    return templates.TemplateResponse(
        request=request,
        name="_stage_list.html",
        context={
            "project": project,
            "handouts": handouts,
            "subject": project.context_json.get("subject", "") if project and project.context_json else "",
            "grade": project.context_json.get("grade", "") if project and project.context_json else "",
            "topic": project.context_json.get("topic", "") if project and project.context_json else ""
        }
    )


@router.get("/{project_id}/stage-list")
async def get_stage_list(
        project_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """HTMX-эндпоинт: возвращает список этапов для проекта"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Handout)
        .where(Handout.project_id == project_id)
        .order_by(Handout.stage_order)
    )
    handouts = result.scalars().all()

    subject = ""
    grade = ""
    topic = ""
    if project.context_json:
        subject = project.context_json.get("subject", "")
        grade = project.context_json.get("grade", "")
        topic = project.context_json.get("topic", "")

    return templates.TemplateResponse(
        request=request,
        name="_stage_list.html",
        context={
            "project": project,
            "handouts": handouts,
            "subject": subject,
            "grade": grade,
            "topic": topic
        }
    )


@router.get("/{project_id}/view-result")
async def view_result(project_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    project = await get_project_with_validation(db, user_id, project_id)

    html_content = markdown.markdown(project.compiled_content, extensions=['tables', 'fenced_code'])

    return templates.TemplateResponse(
        request=request,
        name="view_file.html",
        context={
            "project": project,
            "html_content": html_content,
        }
    )


@router.post("/{project_id}/compile")
async def compile_project(project_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    project = await get_project_with_validation(db, user_id, project_id)

    db_result = await db.execute(
        select(Handout)
        .where(Handout.project_id == project_id)
        .order_by(Handout.stage_order)
    )
    handouts = db_result.scalars().all()

    all_markdown = "\n\n---\n\n".join(f"# {handout.stage_name}\n\n{handout.content}" for handout in handouts)
    all_markdown = re.sub(r'\${2,}(\d+)\${2,}', r'\1', all_markdown)

    project.compiled_content = all_markdown
    project.status = ProjectStatus.EDITING
    await db.commit()

    return await get_project_edit_content_html(project_id, user_id, db, request)


@router.post("/{project_id}/update-content")
async def update_content(
        project_id: int,
        request: Request,
        compiled_content: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    user_id = request.session.get("user_id")
    project = await get_project_with_validation(db, user_id, project_id)

    project.compiled_content = re.sub(r'\${2,}(\d+)\${2,}', r'\1', compiled_content)
    await db.commit()

    return HTMLResponse('<span class="text-green-600">✅ Сохранено</span>')
