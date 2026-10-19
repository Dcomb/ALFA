# frontend/app.py

import os
import time
import uuid

import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="ALFA — AI Assistant",
    page_icon="🤖",
    layout="centered",
)


# =========================
# Session State
# =========================

if "chats" not in st.session_state:
    st.session_state.chats = {}

if "current_chat_id" not in st.session_state:
    chat_id = str(uuid.uuid4())

    st.session_state.current_chat_id = chat_id
    st.session_state.chats[chat_id] = {
        "title": "Новый чат",
        "messages": [],
    }


# =========================
# Chat Management
# =========================

def create_chat():
    chat_id = str(uuid.uuid4())

    st.session_state.chats[chat_id] = {
        "title": "Новый чат",
        "messages": [],
    }

    st.session_state.current_chat_id = chat_id
    st.rerun()


def delete_chat(chat_id: str):
    del st.session_state.chats[chat_id]

    if st.session_state.current_chat_id == chat_id:
        if st.session_state.chats:
            st.session_state.current_chat_id = next(
                reversed(st.session_state.chats)
            )
        else:
            new_id = str(uuid.uuid4())

            st.session_state.chats[new_id] = {
                "title": "Новый чат",
                "messages": [],
            }

            st.session_state.current_chat_id = new_id

    st.rerun()


# =========================
# Sidebar
# =========================

with st.sidebar:
    st.title("ALFA")
    st.caption("Adaptive Lending & Financing Assistant")

    if st.button("＋ Новый чат", use_container_width=True):
        create_chat()

    st.divider()
    st.subheader("История чатов")

    for chat_id, chat in reversed(
        list(st.session_state.chats.items())
    ):
        col_chat, col_delete = st.columns([5, 1])

        with col_chat:
            if st.button(
                chat["title"],
                key=f"chat_{chat_id}",
                use_container_width=True,
            ):
                st.session_state.current_chat_id = chat_id
                st.rerun()

        with col_delete:
            if st.button(
                "🗑️",
                key=f"delete_{chat_id}",
                help="Удалить чат",
            ):
                delete_chat(chat_id)


# =========================
# Current Chat
# =========================

current_chat_id = st.session_state.current_chat_id
current_chat = st.session_state.chats[current_chat_id]

st.title("ALFA")
st.caption("AI-ассистент по кредитованию бизнеса")


# =========================
# Chat History
# =========================

for message in current_chat["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant":
            if "elapsed" in message:
                st.caption(
                    f"⏱ Время ответа API: {message['elapsed']:.2f} сек."
                )


# =========================
# User Input
# =========================

if prompt := st.chat_input("Напишите сообщение..."):

    current_chat["messages"].append({
        "role": "user",
        "content": prompt,
    })

    # Название чата по первому сообщению
    if current_chat["title"] == "Новый чат":
        current_chat["title"] = (
            prompt[:30] + "..." if len(prompt) > 30 else prompt
        )

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("ALFA думает..."):
            start = time.perf_counter()

            try:
                response = requests.post(
                    f"{API_URL}/chat",
                    json={
                        "message": prompt,
                        "thread_id": current_chat_id,
                    },
                    timeout=180,
                )

                response.raise_for_status()

                elapsed = time.perf_counter() - start

                answer = response.json()["response"]

                st.markdown(answer)
                st.caption(
                    f"⏱ Время ответа API: {elapsed:.2f} сек."
                )

                current_chat["messages"].append({
                    "role": "assistant",
                    "content": answer,
                    "elapsed": elapsed,
                })

            except requests.RequestException as e:
                elapsed = time.perf_counter() - start

                st.error(f"Ошибка API: {e}")
                st.caption(
                    f"⏱ Время до ошибки: {elapsed:.2f} сек."
                )