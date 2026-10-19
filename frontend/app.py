import os
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
# Sidebar
# =========================

with st.sidebar:
    st.title("ALFA")
    st.caption("Adaptive Lending & Financing Assistant")

    if st.button("＋ Новый чат", use_container_width=True):
        chat_id = str(uuid.uuid4())

        st.session_state.chats[chat_id] = {
            "title": "Новый чат",
            "messages": [],
        }

        st.session_state.current_chat_id = chat_id
        st.rerun()

    st.divider()

    st.subheader("История чатов")

    for chat_id, chat in reversed(
        list(st.session_state.chats.items())
    ):
        if st.button(
            chat["title"],
            key=chat_id,
            use_container_width=True,
        ):
            st.session_state.current_chat_id = chat_id
            st.rerun()


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
                answer = response.json()["response"]

                st.markdown(answer)

                current_chat["messages"].append({
                    "role": "assistant",
                    "content": answer,
                })

            except requests.RequestException as e:
                st.error(f"Ошибка API: {e}")