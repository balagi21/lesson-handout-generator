from fastapi import UploadFile
from pypdf import PdfReader
from io import BytesIO


async def parse_pdf(file: UploadFile) -> str:
    """
    Извлекает текст из загруженного PDF файла
    """
    content = await file.read()
    reader = PdfReader(BytesIO(content))

    all_text = []
    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text and text.strip():
            all_text.append(f"--- Страница {page_num} ---\n{text.strip()}")

    if not all_text:
        raise ValueError("Не удалось извлечь текст из PDF. Возможно, файл содержит только сканы.")

    return "\n\n".join(all_text)
