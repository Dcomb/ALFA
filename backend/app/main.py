from fastapi import FastAPI

from app.shemas import ChatRequest, ChatResponse
from app.agent.graph import agent

app = FastAPI(title="ALFA API")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await agent.ainvoke(
        {"messages": [("user", request.message)]},
        config={"configurable": {"thread_id": request.thread_id}},
    )

    return ChatResponse(
        response=str(result["messages"][-1].content),
        thread_id=request.thread_id,
    )