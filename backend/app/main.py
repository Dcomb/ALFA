import os

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shemas import ChatResponse, ChatRequest
from app.agent.graph import build_graph
from app.conveyor import models as conveyor_models
from app.conveyor.auth import current_client, own_application
from app.conveyor.db import get_session, init_db
from app.conveyor.schemas import ApplicationBrief, ApplicationOut, ClientBrief, ClientOut
from app.ranking import calculator as calc
from app.ranking.catalog import products
from app.ranking.clients import get_client
from app.ranking.engine import recommend
from app.ranking.schemas import (
    CalcRequest,
    CalcResponse,
    LimitRequest,
    LimitResponse,
    RecommendRequest,
    RecommendResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.environ["DATABASE_URL"]

    init_db()

    async with AsyncPostgresSaver.from_conn_string(
        database_url
    ) as checkpointer:

        await checkpointer.setup()

        app.state.agent = build_graph(checkpointer)

        yield


app = FastAPI(
    title="ALFA API",
    lifespan=lifespan,
)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await app.state.agent.ainvoke(
        {
            "messages": [
                ("user", request.message)
            ]
        },
        config={
            "configurable": {
                "thread_id": request.thread_id
            }
        },
    )

    return ChatResponse(
        response=str(result["messages"][-1].content),
        thread_id=request.thread_id,
    )


def resolve_client(request):
    if request.client is not None:
        return request.client

    client = get_client(request.client_id) if request.client_id else None

    if client is None:
        raise HTTPException(404, f"клиент {request.client_id} не найден")

    return client


@app.get("/ranking/products")
def list_products():
    return products()


@app.post("/ranking/recommend", response_model=RecommendResponse)
def recommend_product(request: RecommendRequest):
    return recommend(
        resolve_client(request),
        request.need,
        request.top_k,
    )


@app.post("/ranking/calculator/payment", response_model=CalcResponse)
def calculate_payment(request: CalcRequest):
    return calc.loan_offer(
        request.amount,
        request.annual_rate,
        request.term_months,
    )


@app.post("/ranking/calculator/limit", response_model=LimitResponse)
def calculate_limit(request: LimitRequest):
    client = resolve_client(request)

    return LimitResponse(
        free_cash_flow=round(calc.free_cash_flow(client), 2),
        max_monthly_payment=round(calc.max_monthly_payment(client), 2),
        max_amount=round(
            calc.max_loan_amount(client, request.annual_rate, request.term_months),
            2,
        ),
    )


@app.get("/clients", response_model=list[ClientBrief])
def list_demo_clients(session: Session = Depends(get_session)):
    return session.scalars(
        select(conveyor_models.Client).order_by(conveyor_models.Client.id)
    ).all()


@app.get("/me", response_model=ClientOut)
def me(client: conveyor_models.Client = Depends(current_client)):
    return client


@app.get("/applications", response_model=list[ApplicationBrief])
def list_applications(
    client: conveyor_models.Client = Depends(current_client),
    session: Session = Depends(get_session),
):
    return session.scalars(
        select(conveyor_models.Application)
        .where(conveyor_models.Application.client_id == client.id)
        .order_by(conveyor_models.Application.id.desc())
    ).all()


@app.get("/applications/{application_id}", response_model=ApplicationOut)
def get_application(
    application: conveyor_models.Application = Depends(own_application),
):
    return application