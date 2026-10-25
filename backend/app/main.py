import logging
import os

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.output import sanitize_answer_links
from app.shemas import ChatResponse, ChatRequest
from app.agent.graph import build_graph
from app.conveyor import lifecycle
from app.conveyor import models as conveyor_models
from app.conveyor.auth import any_application, bank_employee, current_client, own_application
from app.conveyor.schemas import (
    AcceptOffer,
    ApplicationBrief,
    ApplicationCreate,
    ApplicationOut,
    ApplicationUpdate,
    BankApplicationBrief,
    BankApplicationOut,
    ClientBrief,
    ClientOut,
    ProcessingOut,
    Status,
)
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
from app.conveyor.db import (
    SessionLocal,
    get_session,
    init_db,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


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


@app.exception_handler(lifecycle.ConveyorError)
def conveyor_error(request: Request, error: lifecycle.ConveyorError):
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.message, **error.details},
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    with SessionLocal() as session:
        client = session.get(
            conveyor_models.Client,
            request.client_id,
        )

        if client is None:
            raise HTTPException(
                status_code=401,
                detail="клиент не найден",
            )

    result = await app.state.agent.ainvoke(
        {
            "messages": [
                ("user", request.message),
            ],
        },
        config={
            "configurable": {
                # Разделяем историю разных клиентов.
                "thread_id": (
                    f"{request.client_id}:"
                    f"{request.thread_id}"
                ),
                # Tools получают клиента отсюда,
                # а не из аргументов LLM.
                "client_id": request.client_id,
            },
        },
    )

    answer = str(result["messages"][-1].content)

    return ChatResponse(
        response=sanitize_answer_links(answer),
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


@app.post("/applications", response_model=ApplicationOut, status_code=201)
def create_application(
    request: ApplicationCreate,
    client: conveyor_models.Client = Depends(current_client),
    session: Session = Depends(get_session),
):
    return lifecycle.create(session, client, request.model_dump(exclude_none=True))


@app.get("/applications/{application_id}", response_model=ApplicationOut)
def get_application(
    application: conveyor_models.Application = Depends(own_application),
):
    return application


@app.get("/applications/{application_id}/processing", response_model=ProcessingOut)
def get_processing(
    application: conveyor_models.Application = Depends(own_application),
):
    return application


@app.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application(
    request: ApplicationUpdate,
    application: conveyor_models.Application = Depends(own_application),
    client: conveyor_models.Client = Depends(current_client),
    session: Session = Depends(get_session),
):
    return lifecycle.update(session, client, application, request.model_dump(exclude_unset=True))


@app.post("/applications/{application_id}/submit", response_model=ApplicationOut)
def submit_application(
    application: conveyor_models.Application = Depends(own_application),
    client: conveyor_models.Client = Depends(current_client),
    session: Session = Depends(get_session),
):
    lifecycle.submit(session, client, application)
    return lifecycle.run_checks(session, client, application)


@app.post("/applications/{application_id}/process", response_model=ApplicationOut)
def process_application(
    application: conveyor_models.Application = Depends(own_application),
    client: conveyor_models.Client = Depends(current_client),
    session: Session = Depends(get_session),
):
    return lifecycle.run_checks(session, client, application)


@app.post("/applications/{application_id}/accept", response_model=ApplicationOut)
def accept_offer(
    request: AcceptOffer,
    application: conveyor_models.Application = Depends(own_application),
    session: Session = Depends(get_session),
):
    return lifecycle.accept_offer(session, application, request.option)


@app.post("/applications/{application_id}/decline-offer", response_model=ApplicationOut)
def decline_offer(
    application: conveyor_models.Application = Depends(own_application),
    session: Session = Depends(get_session),
):
    return lifecycle.decline_offer(session, application)


@app.post("/applications/{application_id}/withdraw", response_model=ApplicationOut)
def withdraw_application(
    application: conveyor_models.Application = Depends(own_application),
    session: Session = Depends(get_session),
):
    return lifecycle.withdraw(session, application)

@app.get("/bank/applications", response_model=list[BankApplicationBrief])
def bank_list_applications(
    status: Status | None = None,
    client_id: str | None = None,
    _: None = Depends(bank_employee),
    session: Session = Depends(get_session),
):
    query = select(conveyor_models.Application).order_by(conveyor_models.Application.updated_at.desc())

    if status is not None:
        query = query.where(conveyor_models.Application.status == status)
    if client_id is not None:
        query = query.where(conveyor_models.Application.client_id == client_id)

    return session.scalars(query).all()


@app.get("/bank/applications/{application_id}", response_model=BankApplicationOut)
def bank_get_application(
    application: conveyor_models.Application = Depends(any_application),
):
    return application
