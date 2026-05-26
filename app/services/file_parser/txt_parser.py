from fastapi import UploadFile

async def parse_txt(file: UploadFile) -> str:
    """
    Извлекает текст из загруженного TXT файла
    """
    content = await file.read()
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("cp1251")
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="replace")
