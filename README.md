# 🌐 Site Analyzer (Tracer)

**Веб-приложение для комплексного анализа сайтов и сетевых протоколов.**

Разработано студентами БГУИР. Приложение выполняет полный аудит веб-сайта: проверяет SSL-сертификаты, DNS-записи, HTTP-заголовки, безопасность, открытые порты, маршрутизацию и многое другое.

---

## 📋 Содержание

- [Возможности](#-возможности)
- [Установка](#-установка)
- [Запуск](#-запуск)
- [Структура проекта](#-структура-проекта)
- [API](#-api)
- [Тестирование](#-тестирование)
- [Скрипты](#-скрипты)
- [Технологии](#-технологии)

---

## ✨ Возможности

### Анализ

| Модуль | Описание |
|--------|----------|
| **SSL/TLS** | Сертификат, издатель, протокол, шифр, срок действия |
| **DNS** | Записи A, AAAA, MX, NS, TXT, CNAME |
| **HTTP-заголовки** | Полный список заголовков ответа |
| **Безопасность** | Автоматический скоринг (0–100), оценка A–F |
| **Cookies** | Проверка флагов Secure, HttpOnly, SameSite |
| **Технологии** | Определение фреймворков, CMS, серверов |
| **Производительность** | TTFB, время загрузки, размер контента |
| **WHOIS** | Домен, регистратор, даты создания и истечения |
| **Порты** | Сканирование 18+ портов (HTTP, SSH, MySQL и др.) |
| **Traceroute** | Маршрут до хоста с хопами и RTT |

### Функции приложения

- **Сохранение анализов** — сохраняйте результаты с заметками
- **История сканирований** — последние 100 проанализированных URL
- **Повторный анализ** — быстрый перезапуск из сохранённых или истории

---

## 🚀 Установка

### Требования

- Python 3.10+
- pip

### Шаги

```bash
# Клонирование репозитория
git clone https://github.com/Bogdaniam20/Tracer.git
cd Tracer

# Создание виртуального окружения (рекомендуется)
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# Установка зависимостей
pip install -r requirements.txt
```

---

## ▶️ Запуск

```bash
python main.py
```

Приложение будет доступно по адресу: **http://localhost:8000**

Для разработки с автоперезагрузкой (режим по умолчанию):

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📁 Структура проекта

```
Tracer/
├── main.py                 # Точка входа FastAPI
├── requirements.txt        # Зависимости Python
├── pytest.ini              # Конфигурация pytest
├── README.md
│
├── app/
│   ├── analyzer.py        # Логика анализа (DNS, SSL, headers, cookies, tech)
│   ├── models.py          # Pydantic-модели данных
│   ├── protocols.py       # SSL, порты, traceroute
│   ├── storage.py         # Сохранение и история сканирований
│   │
│   ├── templates/         # Jinja2 шаблоны
│   │   ├── base.html
│   │   ├── index.html     # Главная — анализ
│   │   ├── saved.html     # Сохранённые сайты
│   │   └── history.html   # История сканирований
│   │
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js
│           ├── saved.js
│           └── history.js
│
├── data/                   # JSON-хранилище (создаётся автоматически)
│   ├── saved_sites.json
│   └── scan_history.json
│
├── scripts/
│   └── generate_tech_debt_report.py   # Генерация PDF-отчёта
│
├── reports/                # Сгенерированные PDF (создаётся автоматически)
│   └── technical_debt_report.pdf
│
└── tests/
    ├── conftest.py
    ├── test_analyzer.py
    ├── test_api.py
    ├── test_scan_port.py
    └── test_storage.py
```

---

## 🛠 API

### Анализ

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/analyze` | Полный анализ сайта по URL |

**Тело запроса:**
```json
{
  "url": "example.com"
}
```

Возвращает полный JSON-отчёт: `url`, `ip_address`, `dns`, `ssl`, `headers`, `security`, `technologies`, `performance`, `whois`, `ports`, `traceroute`, `cookies`, `error`.

---

### Сохранённые сайты

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/saved` | Список сохранённых |
| `POST` | `/api/saved` | Сохранить анализ |
| `DELETE` | `/api/saved/{id}` | Удалить сохранённый сайт |
| `PATCH` | `/api/saved/{id}/note` | Обновить заметку |

---

### История

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/history?limit=50` | Список последних сканирований |

---

### Служебные

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/health` | Проверка состояния сервиса |

---

## 🧪 Тестирование

```bash
# Все тесты
python -m pytest -v

# Из корня проекта
cd Tracer
python -m pytest tests/ -v

# Конкретный модуль
python -m pytest tests/test_analyzer.py -v

# С покрытием (если установлен pytest-cov)
python -m pytest --cov=app -v
```

---

## 📄 Скрипты

### Генерация PDF-отчёта о техническом долге

```bash
python scripts/generate_tech_debt_report.py
```

Создаёт файл `reports/technical_debt_report.pdf` с графиками и сводкой по техническому долгу.

---

## 🛠 Технологии

| Категория | Стек |
|-----------|------|
| **Backend** | Python 3, FastAPI, Uvicorn |
| **HTTP-клиент** | httpx |
| **DNS** | dnspython |
| **WHOIS** | python-whois |
| **Парсинг HTML** | BeautifulSoup4, lxml |
| **Валидация** | Pydantic |
| **Тестирование** | pytest, pytest-asyncio |
| **Графики** | matplotlib |

---

## 📜 Лицензия

© 2026 БГУИР. Студенческий проект.

---

## 👥 Авторы

Студенты БГУИР — Site Analyzer (Tracer)
