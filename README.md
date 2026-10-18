<div align="center">

# ALFA

### Adaptive Lending & Financing Assistant

**Умный кредитный кабинет предпринимателя с AI-ассистентом для малого и микробизнеса**

[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Orchestration-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![LangChain](https://img.shields.io/badge/LangChain-LLM-1C3C3C)](https://www.langchain.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

**Проект для АльфаХакатона · Направление: малый и микробизнес (ММБ)**

</div>

---

## О проекте

**ALFA — Adaptive Lending & Financing Assistant** — рабочее название проекта умного кредитного кабинета предпринимателя.

Кейс АльфаХакатона: **«Умный кредитный кабинет предпринимателя»**.

Задача — разработать личный кабинет для сегмента малого и микробизнеса с AI-ассистентом, который понимает потребности клиента, помогает подобрать подходящий кредитный продукт и пройти путь от подачи заявки до решения.

> **Статус:** проект находится на этапе проектирования. Описанные ниже возможности и архитектура — план реализации, а не заявление о готовом функционале.

---

## Планируемые возможности

- Личный кабинет предпринимателя с несколькими разделами.
- Диалог с AI-ассистентом для уточнения кредитных потребностей.
- Подбор кредитных продуктов с помощью рекомендательной системы.
- Использование классического ML для кредитного скоринга.
- Помощь в заполнении кредитной заявки.
- Просмотр заявки и её статуса.

---

## Архитектура

Планируемая архитектура — **monorepo + модульный монолит**: Streamlit как интерфейс, FastAPI как backend, LangGraph/LangChain для AI-ассистента, Python-модули для рекомендаций и скоринга.

```text
                       ┌──────────────────────┐
                       │       Streamlit      │
                       │   Личный кабинет     │
                       └──────────┬───────────┘
                                  │ HTTP API
                                  ▼
                       ┌──────────────────────┐
                       │        FastAPI       │
                       │ Backend / API        │
                       └──────────┬───────────┘
                                  │
                 ┌────────────────┼─────────────────┐
                 │                │                 │
                 ▼                ▼                 ▼
        ┌────────────────┐ ┌───────────────┐ ┌──────────────┐
        │ AI Assistant   │ │ Recommender   │ │ Credit       │
        │ LangGraph      │ │               │ │ Scoring      │
        │ LangChain      │ │               │ │              │
        └────────┬───────┘ └───────────────┘ └──────────────┘
                 │
                 └── Tool Calling → ML-модули и бизнес-логика
```

**Docker Compose** планируется использовать для запуска компонентов приложения. Взаимодействие между интерфейсом и backend предполагается через HTTP API; скоринг и рекомендации — Python-модули внутри backend, без отдельных микросервисов.

### AI-ассистент

Планируемая ответственность AI-части:

- обработка запросов предпринимателя;
- сбор и уточнение параметров заявки;
- управление состоянием диалога через LangGraph;
- вызов доступных инструментов через Tool Calling;
- объяснение подобранных предложений.

### Recommendation System

Модуль для подбора и ранжирования кредитных продуктов на основе потребностей предпринимателя. Конкретный алгоритм пока не зафиксирован.

### Credit Scoring

Модуль классического ML для оценки кредитного риска. Модель, признаки и способ обучения будут определяться доступностью данных.

---

## Технологический стек

| Категория | Планируемые технологии |
| --- | --- |
| Язык разработки | Python |
| Frontend | Streamlit |
| Backend / API | FastAPI |
| AI orchestration | LangGraph |
| LLM integration | LangChain |
| Вызов ML-компонентов | Tool Calling / Python |
| Scoring | Классический ML (алгоритм уточняется) |
| Recommendation System | Python (алгоритм уточняется) |
| Контейнеризация | Docker, Docker Compose |

Выбор конкретной LLM, хранилища данных и алгоритмов ML пока не зафиксирован.

---

## Планируемая структура проекта

```text
alfa-hackathon/
│
├── frontend/                   # Streamlit
│   ├── app.py
│   ├── pages/
│   │   ├── dashboard.py
│   │   ├── assistant.py
│   │   └── applications.py
│   └── api.py
│
├── backend/                    # FastAPI
│   └── app/
│       ├── main.py
│       ├── agent/              # LangGraph / LangChain
│       │   ├── graph.py
│       │   ├── state.py
│       │   └── tools.py
│       ├── scoring/
│       │   └── inference.py
│       ├── recommender/
│       │   └── inference.py
│       └── schemas.py         # Общие контракты данных
│
├── ml/                         # Эксперименты и обучение
│   ├── scoring/
│   └── recommender/
│
├── data/                       # Данные проекта
├── tests/                      # Тесты
├── docker-compose.yml
└── README.md
```

Структура предварительная и может меняться в ходе разработки.

---

## Команда

| Участник | Направление |
| --- | --- |
| **Егор Шипилов** | ML / LLM / AI Engineer — AI-ассистент, LangGraph, LangChain, Tool Calling |
| **Елена Елисеева** | Business Analysis, UX/UI и дизайн; интерфейс на Streamlit — в плане |
| **Никита Кирнасов** | Recommendation System |
| **Анастасия Корнева** | Классический ML, кредитный скоринг |
| **Анастасия Антонова** | Классический ML, кредитный скоринг; помощь в разработке AI-части |

---

## Статус проекта

**Проектирование / подготовка к реализации.**

Определены кейс, распределение основных направлений в команде и предварительный технологический стек. Реализация и интеграция компонентов — следующие этапы.
