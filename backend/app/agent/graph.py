import os

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import MessagesState, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS


llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL"),
    base_url=os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434",
    ),
    temperature=0,
    num_ctx=8192,
    keep_alive=-1,
)

llm_with_tools = llm.bind_tools(TOOLS)


async def chatbot(state: MessagesState):
    response = await llm_with_tools.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
    ])

    return {
        "messages": [response],
    }


def build_graph(checkpointer):
    graph = StateGraph(MessagesState)

    graph.add_node("chatbot", chatbot)
    graph.add_node(
        "tools",
        ToolNode(
            TOOLS,
            handle_tool_errors=(
                "Инструмент временно недоступен. "
                "Объясни проблему пользователю и не "
                "придумывай результат."
            ),
        ),
    )

    graph.add_edge(START, "chatbot")
    graph.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph.add_edge("tools", "chatbot")

    return graph.compile(
        checkpointer=checkpointer,
    )