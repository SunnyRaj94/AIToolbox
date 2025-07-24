# src/aitoolkit/frontend/main.py
import streamlit as st
import asyncio
from aitoolkit.config import configs, env # Import our configuration
from aitoolkit.backend.llm import LLM_REGISTRY, BaseLLM # Import LLM_REGISTRY and BaseLLM
from aitoolkit.frontend.components.pages.sql_agent_page import sql_agent_page # Import the new page

PAGE_TITLE = configs.get("app")['project_name']
PAGE_ICON = configs.get("app")['title_icon']
LAYOUT = configs.get("app")['layout']
INITIAL_SIDEBAR_STATUS = configs.get("app")['sidebar_state']
DEBUG_MODE = configs.get("app")['debug_mode']

# --- Configure Streamlit Page ---
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state=INITIAL_SIDEBAR_STATUS
)

# --- Session State Initialization ---
# 'messages' for the general LLM test chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# 'current_llm' stores the active LLM instance (e.g., OpenAI_LLM, Groq_LLM)
if "current_llm" not in st.session_state:
    st.session_state.current_llm = None

# Track the selected provider and model to know when to re-initialize the LLM
if "current_llm_provider" not in st.session_state:
    st.session_state.current_llm_provider = None
if "current_llm_model" not in st.session_state:
    st.session_state.current_llm_model = None

# --- Main Application Logic ---
async def main():
    st.title(f"{PAGE_TITLE} {PAGE_ICON}")
    st.write("Welcome to your AI-Powered Productivity Hub!")
    st.write(f"Debug Mode: {DEBUG_MODE}")

    st.sidebar.header("Global Settings")

    # --- LLM Provider Selection ---
    available_providers = configs.get('llm_settings', {}).get('available_providers', [])
    default_provider = configs.get('llm_settings').get('default_provider')
    default_index = available_providers.index(default_provider) if default_provider in available_providers else 0

    selected_provider = st.sidebar.selectbox(
        "Select LLM Provider:",
        options=available_providers,
        index=default_index,
        key="llm_provider_selection"
    )

    # --- Dynamic Model Selection based on Provider ---
    selected_model = None
    if selected_provider == "OpenAI":
        selected_model = st.sidebar.text_input(
            "OpenAI Model:",
            value=configs.get('llm_settings').get('openai_default_model'),
            key="openai_model_input"
        )
    elif selected_provider == "Groq":
        selected_model = st.sidebar.text_input(
            "Groq Model:",
            value=configs.get('llm_settings').get('groq_default_model'),
            key="groq_model_input"
        )
    elif selected_provider == "Ollama":
        selected_model = st.sidebar.text_input(
            "Ollama Model:",
            value=configs.get('llm_settings').get('ollama_default_model'),
            key="ollama_model_input"
        )
    # Add more elif for other providers (e.g., "Google Gemini")

    st.sidebar.info(f"Using {selected_model} from {selected_provider}")

    # --- Initialize/Update current LLM instance in session state ---
    # Re-initialize current_llm only if the selected provider or model has changed
    # compared to the one currently stored in session state.
    if (st.session_state.current_llm is None or
        st.session_state.current_llm_provider != selected_provider or
        st.session_state.current_llm_model != selected_model):

        # Update the tracked provider and model
        st.session_state.current_llm_provider = selected_provider
        st.session_state.current_llm_model = selected_model

        if selected_model:
            llm_class = LLM_REGISTRY.get(selected_provider)
            if llm_class:
                try:
                    # Directly instantiate the LLM and store it in session state
                    st.session_state.current_llm = llm_class(model_name=selected_model)
                except ValueError as e:
                    # If there's an error (e.g., missing API key), set LLM to None
                    st.error(f"Error initializing {selected_provider} LLM: {e}")
                    st.session_state.current_llm = None
            else:
                st.error(f"Unknown LLM provider: {selected_provider}")
                st.session_state.current_llm = None
        else:
            # If no model is selected, ensure no LLM instance is active
            st.session_state.current_llm = None

    # --- Display API Keys Status (updated to use current_llm) ---
    if st.session_state.current_llm:
        llm_info = st.session_state.current_llm.get_model_info()
        if llm_info.get("api_key_set"):
            st.sidebar.success(f"{llm_info['provider']} API Key is set!")
        elif llm_info.get("provider") not in ["Ollama"]:
            # Ollama typically runs locally and doesn't require a traditional API key
            st.sidebar.warning(f"{llm_info['provider']} API Key is NOT set. Please set the appropriate environment variable.")
    else:
        st.sidebar.warning("LLM instance not initialized. Please ensure a model is selected and any required API keys are set.")

    st.markdown("---")

    # --- Agent Tabs ---
    # Using st.tabs to organize different agents
    tab1, tab2 = st.tabs(["LLM Test Chat", "SQL Agent"]) # Add more tabs as agents are built

    with tab1:
        st.header("LLM Interaction Test")
        st.write("Use this section to test the selected LLM provider and model.")

        # Display chat messages from history stored in session state
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input for user interaction
        if prompt := st.chat_input("Ask something to your selected LLM...", key="test_llm_chat_input"):
            # Add user's message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate and stream response from the current LLM
            if st.session_state.current_llm:
                with st.chat_message("assistant"):
                    message_placeholder = st.empty() # Placeholder for streaming output
                    full_response = ""
                    try:
                        async for chunk in st.session_state.current_llm.stream_response(prompt):
                            full_response += chunk
                            # Update placeholder with new chunk and a blinking cursor
                            message_placeholder.markdown(full_response + "▌")
                        message_placeholder.markdown(full_response) # Final rendering without cursor
                    except Exception as e:
                        st.error(f"Error during streaming: {e}")
                        full_response = f"An error occurred: {e}"
                # Add assistant's full response to chat history
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            else:
                with st.chat_message("assistant"):
                    st.warning("Please select and initialize an LLM provider in the sidebar.")

    with tab2:
        # Pass the current LLM instance to the SQL Agent page.
        # Since sql_agent_page is now async, it must be awaited.
        await sql_agent_page(st.session_state.current_llm)


if __name__ == "__main__":
    # Run the main asynchronous Streamlit application
    asyncio.run(main())