import markdown
import weasyprint
from io import BytesIO
from urllib.parse import quote
from fastapi import APIRouter, Request, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete, update
from pydantic import BaseModel
from typing import List
from datetime import datetime, UTC

from ..services.llm import llm_gigachat
from ..database import get_db
from ..models.project import Project, ProjectStatus
from ..models.handout import Handout
from ..models.export import ExportedPDF


router = APIRouter(prefix="/projects", tags=["projects"])
templates = Jinja2Templates(directory="app/templates")


class GeneratePlanPromptRequest(BaseModel):
    prompt: str


class ReorderRequest(BaseModel):
    handout_id: int
    new_order: int


class UpdateStageRequest(BaseModel):
    name: str
    description: str
    handout_type: str


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
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={"message": "Урок не найден"},
            status_code=404
        )

    # Проверяем, есть ли этапы у проекта
    handouts_result = await db.execute(
        select(Handout).where(Handout.project_id == project_id)
    )
    handouts = handouts_result.scalars().all()
    all_handouts_generated = all(h.status == 'ready' for h in handouts)
    has_pdf = False
    if all_handouts_generated:
        db_result = await db.execute(
            select(ExportedPDF).where(ExportedPDF.project_id == project_id)
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


@router.post("/{project_id}/delete")
async def delete_project(
        project_id: int,
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Удаление проекта"""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "Unauthorized"}, 401

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()

    if project:
        await db.delete(project)
        await db.commit()

    return RedirectResponse(url="/projects/", status_code=303)


@router.post("/{project_id}/generate-plan-from-prompt")
async def generate_plan_from_prompt(
        project_id: int,
        request: Request,
        data: GeneratePlanPromptRequest,
        db: AsyncSession = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    llm_result = llm_gigachat.generate_plan_from_prompt(data.prompt)

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
            handout_type=stage.handout_type,
            status="pending"
        )
        db.add(handout)

    await db.commit()

    return await get_project_edit_content_html(project_id, user_id, db, request)


@router.post("/{project_id}/generate-plan-from-file")
async def generate_plan_from_file(
        project_id: int,
        request: Request,
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Заглушка: данные из файла
    subject = "Русский язык"
    grade = "6"
    topic = "Имя существительное: падежи и склонения"

    stages_data = [
        {"name": "Введение в тему", "description": "Постановка целей и задач урока"},
        {"name": "Теоретическая часть", "description": "Лекция с презентацией, основные определения"},
        {"name": "Практическая работа", "description": "Решение задач у доски и в тетрадях"},
        {"name": "Проверка понимания", "description": "Самостоятельная работа с взаимопроверкой"},
        {"name": "Домашнее задание", "description": "Объяснение домашнего задания, комментарии"}
    ]

    # Сохраняем метаданные
    context = project.context_json or {}
    context["subject"] = subject
    context["grade"] = grade
    context["topic"] = topic
    context["generated_from"] = "file"
    context["original_filename"] = file.filename
    project.context_json = context
    await db.commit()

    # Удаляем существующие этапы
    await db.execute(
        delete(Handout).where(Handout.project_id == project_id)
    )

    # Сохраняем новые этапы
    for idx, stage in enumerate(stages_data):
        handout = Handout(
            project_id=project_id,
            stage_order=idx,
            stage_name=stage["name"],
            stage_description=stage["description"],
            handout_type="work_sheet",
            status="pending"
        )
        db.add(handout)

    await db.commit()

    return await get_stage_list_html(project_id, user_id, db, request)


@router.post("/{project_id}/handouts/reorder")
async def reorder_handouts(
        project_id: int,
        request: Request,
        orders: List[ReorderRequest],
        db: AsyncSession = Depends(get_db)
):
    """Изменение порядка этапов"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Проверяем доступ к проекту
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

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
        handout_type: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    """Обновление этапа (имя, описание, тип)"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db_result = await db.execute(select(Project).where(Project.id == project_id))
    project_info = db_result.scalar_one_or_none()
    if not project_info:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Handout).where(Handout.id == handout_id, Handout.project_id == project_id)
    )
    handout = result.scalar_one_or_none()
    if not handout:
        raise HTTPException(status_code=404, detail="Handout not found")

    handout.stage_name = name
    handout.stage_description = description
    handout.handout_type = handout_type
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
    return await get_stage_list_html(project_id, user_id, db, request)


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
        handout_type="work_sheet",
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
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db_result = await db.execute(select(Project).where(Project.id == project_id))
    project_info = db_result.scalar_one_or_none()
    if not project_info:
        raise HTTPException(status_code=404, detail="Project not found")
    if project_info.user_id != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db_result = await db.execute(
        select(Handout).where(Handout.id == handout_id, Handout.project_id == project_id)
    )
    handout = db_result.scalar_one_or_none()
    if not handout:
        raise HTTPException(status_code=404, detail="Handout not found")

    # Обновляем статус
    handout.status = "generating"
    await db.commit()

    llm_response = llm_gigachat.generate_handout(
        subject=project_info.context_json["subject"],
        grade=project_info.context_json["grade"],
        topic=project_info.context_json["topic"],
        handout_type=handout.handout_type,
        description=handout.stage_description
    )

    handout.content = llm_response.content
    handout.status = "ready"
    handout.generated_at = datetime.now(UTC)
    await db.commit()

    all_generated = await check_all_handouts_generated(project_id, db)

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


async def get_project_edit_content_html(project_id: int, user_id: int, db: AsyncSession, request: Request):
    """Вспомогательная функция: возвращает HTML-фрагмент содержимого страницы редактирования проекта"""
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


@router.post("/{project_id}/export-pdf")
async def export_pdf(project_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = db_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db_result = await db.execute(
        select(Handout)
        .where(Handout.project_id == project_id)
        .order_by(Handout.stage_order)
    )
    handouts = db_result.scalars().all()

    all_markdown = ""
    for handout in handouts:
        all_markdown += f"# {handout.stage_name}\n\n{handout.content}\n\n---\n\n"

    html_content = markdown.markdown(all_markdown, extensions=['tables', 'fenced_code'])

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{project.name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 2cm; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; }}
            h2 {{ color: #34495e; margin-top: 1.5em; }}
            table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
            pre {{ background-color: #f4f4f4; padding: 1em; border-radius: 4px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    pdf_buffer = BytesIO()
    weasyprint.HTML(string=full_html).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    pdf_bytes = pdf_buffer.getvalue()

    db_result = await db.execute(
        select(ExportedPDF).where(ExportedPDF.project_id == project_id)
    )
    existing_pdf = db_result.scalar_one_or_none()

    if existing_pdf:
        existing_pdf.pdf_data = pdf_bytes
        existing_pdf.updated_at = datetime.now(UTC)
    else:
        new_pdf = ExportedPDF(
            project_id=project_id,
            pdf_data=pdf_bytes
        )
        db.add(new_pdf)

    await db.commit()

    response = Response()
    response.headers["HX-Trigger"] = "pdf-ready"
    return response


@router.get("/{project_id}/download-pdf")
async def download_pdf(project_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = db_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db_result = await db.execute(
        select(ExportedPDF).where(ExportedPDF.project_id == project_id)
    )
    existing_pdf = db_result.scalar_one_or_none()
    if not existing_pdf:
        raise HTTPException(status_code=404, detail="File not found")

    return Response(
        content=existing_pdf.pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={quote(project.name)}.pdf"}
    )
