from fastapi import UploadFile
from .txt_parser import parse_txt
from .pdf_parser import parse_pdf
from .docx_parser import parse_docx

async def extract_text(file: UploadFile) -> str:
    """
    Определяет тип файла по расширению и извлекает текст.
    """
    filename = file.filename.lower()
    if filename.endswith('.txt'):
        return await parse_txt(file)
    elif filename.endswith('.pdf'):
        return await parse_pdf(file)
    elif filename.endswith('.docx'):
        return await parse_docx(file)
    else:
        raise ValueError(f"Unsupported file type: {filename}")
