# Lesson Handout Generator

Сервис для автоматической генерации раздаточных материалов к уроку с использованием LLM. Разработан в рамках хакатона "ИИ для образования" (подробнее - в [hackaton.md](docs/hackaton.md))

## Инструкция по запуску

1. Установить Docker
2. Получить API ключ GigaChat [https://developers.sber.ru/](https://developers.sber.ru/)
3. Выполнить скрипт: *./run.sh* Скрипт соберёт Docker-контейнер из исходников и запустит его
4. По запросу скрипта, ввести ключ API GigaChat
5. Сервис будет доступен по адресу: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Разработка и локальный запуск без Docker

1. Создать и активировать виртуальное окружение

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Настроить переменные окружения: скопировать файл *.env.example* как *.env* и заполнить параметры
    - **SECRET_KEY**: строка из 64 символов, получить командой *openssl rand -hex 32*
	- **GIGACHAT_API_KEY**: API ключ GigaChat
3. Запустить сервер командой *fastapi dev app/main.py*

## Возможности

TBD

## Технологии

- FastAPI + Jinja2 + HTMX
- GigaChat API
- SQLite + SQLAlchemy

## Документация

- [Продуктовое исследование](docs/product_research.md)
- [Архитектура и стек](docs/architecture.md)
- [Дорожная карта](docs/roadmap.md)
- [Сравнение с аналогами](docs/comparison.md)
- [Риски и меры](docs/risks.md)
