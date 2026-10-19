import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.shemas import ChatResponse, ChatRequest
from app.agent.graph import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.environ["DATABASE_URL"]

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