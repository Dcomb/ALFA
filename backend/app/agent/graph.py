import os

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage

from langchain_ollama import ChatOllama

from app.agent.tools import get_score, recommend_product
from app.agent.prompts import SYSTEM_PROMPT

llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL"),
    base_url=os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434",
    ),
    temperature=0,
    num_ctx=8192,
)

tools = [get_score, recommend_product]

llm_with_tools = llm.bind_tools(tools)


async def chatbot(state: MessagesState):
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
    ]

    response = await llm_with_tools.ainvoke(
        messages
    )

    return {"messages": [response]}


def build_graph():
    graph = StateGraph(MessagesState)

    graph.add_node("chatbot", chatbot)
    graph.add_node("tools", ToolNode(tools))

    graph.add_edge(START, "chatbot")

    graph.add_conditional_edges(
        "chatbot",
        tools_condition,
    )

    graph.add_edge("tools", "chatbot")

    return graph.compile()


agent = build_graph()