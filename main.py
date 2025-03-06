from typing import Set

from core import run_llm
from onchain_tx_execution import stake
import streamlit as st

st.header("Butter Fi")
# st.text("Recommend 3 staking protocols for me, at least 5% APR.")

if "protocols" not in st.session_state:
    st.session_state.protocols = []
if "selected_protocol" not in st.session_state:
    st.session_state.selected_protocol = None
if "show_stake_input" not in st.session_state:
    st.session_state.show_stake_input = False

prompt = st.chat_input("What do you want to ask me today?")

if (
    "chat_answers_history" not in st.session_state
    and "user_prompt_history" not in st.session_state
    and "chat_history" not in st.session_state
):
    st.session_state["chat_answers_history"] = []
    st.session_state["user_prompt_history"] = []
    st.session_state["chat_history"] = []

if prompt:
    with st.spinner("Generating response.."):
        llm_response = run_llm(
            query=prompt, chat_history=st.session_state["chat_history"]
        )
        formatted_response = (
            f"{llm_response['answer']}"
        )
        
        # Store protocols in session state
        st.session_state.protocols = llm_response["protocols"]

        st.session_state["user_prompt_history"].append(prompt)
        st.session_state["chat_answers_history"].append(formatted_response)
        st.session_state["chat_history"].append(("human", prompt))
        st.session_state["chat_history"].append(("ai", llm_response["answer"]))


if st.session_state["chat_answers_history"]:
    for llm_response, user_query in zip(
        st.session_state["chat_answers_history"],
        st.session_state["user_prompt_history"],
    ):
        st.chat_message("user").write(user_query)
        st.chat_message("assistant").write(llm_response)

# Move protocol buttons outside if prompt block
if st.session_state.protocols:
    protocol_container = st.container()
    with protocol_container:
        cols = st.columns(len(st.session_state.protocols), gap="small")
        for idx, protocol in enumerate(st.session_state.protocols):
            with cols[idx]:
                if st.button(f" Earn on {protocol}", key=f"protocol_{idx}"):
                    st.session_state.selected_protocol = protocol
                    st.session_state.show_stake_input = True

# Show stake input form when protocol is selected
if st.session_state.show_stake_input:
    with st.form("stake_form"):
        stake_amount = st.number_input(
            f"Enter amount to stake in {st.session_state.selected_protocol}",
            min_value=0.0,
            step=0.1,
        )
        submit_stake = st.form_submit_button("Confirm Stake")

        if submit_stake:
            st.info(
                f"Staking {stake_amount} ETH in {st.session_state.selected_protocol}..."
            )
            tx_hash = stake(stake_amount)
            st.success(f"Stake successful! Transaction Hash: {tx_hash}")
            st.session_state.show_stake_input = False
