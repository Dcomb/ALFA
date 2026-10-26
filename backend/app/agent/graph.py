import os

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS


def configured_llm():
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    model = os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL")

    if provider == "openai_compatible":
        return ChatOpenAI(
            model=model,
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("LLM_API_KEY", "ollama"),
            temperature=0,
        )

    if provider != "ollama":
        raise ValueError("LLM_PROVIDER должен быть ollama или openai_compatible")

    return ChatOllama(
        model=model,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
        num_ctx=int(os.getenv("LLM_CONTEXT_SIZE", "8192")),
        keep_alive=-1,
    )


llm = configured_llm()

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
