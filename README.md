# Lesson Handout Generator

Сервис для автоматической генерации раздаточных материалов к уроку с использованием LLM. Разработан в рамках хакатона "ИИ для образования" (подробнее - в [hackaton.md](docs/hackaton.md))

## Инструкция по запуску

1. Установить Docker
2. Получить API ключ GigaChat [https://developers.sber.ru/](https://developers.sber.ru/)
3. Выполнить скрипт: *./run.sh* Скрипт соберёт Docker-контейнер из исходников и запустит его
4. По запросу скрипта, ввести ключ API GigaChat
5. Сервис будет доступен по адресу: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

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
