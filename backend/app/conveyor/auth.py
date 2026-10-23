from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_session
from .models import Application, Client


def current_client(
    x_client_id: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Client:
    if not x_client_id:
        raise HTTPException(401, "не указан клиент: заголовок X-Client-Id")

    client = session.get(Client, x_client_id)

    if client is None:
        raise HTTPException(401, "клиент не найден")

    return client


def bank_employee(x_role: str | None = Header(default=None)):
    if x_role != "bank":
        raise HTTPException(403, "нужна роль сотрудника банка: заголовок X-Role: bank")


def any_application(
    application_id: int,
    _: None = Depends(bank_employee),
    session: Session = Depends(get_session),
) -> Application:
    application = session.get(Application, application_id)

    if application is None:
        raise HTTPException(404, "заявка не найдена")

    return application


def own_application(
    application_id: int,
    client: Client = Depends(current_client),
    session: Session = Depends(get_session),
) -> Application:
    application = session.get(Application, application_id)

    if application is None or application.client_id != client.id:
        raise HTTPException(404, "заявка не найдена")

    return application
