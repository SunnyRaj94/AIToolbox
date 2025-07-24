# src/aitoolkit/frontend/components/pages/sql_agent_page.py
import streamlit as st
import asyncio # Although not directly used for await, good to keep for context if more async is added
from aitoolkit.backend.llm import BaseLLM
from aitoolkit.backend.db import SchemaManager
from aitoolkit.backend.agents import SQLAgent
from aitoolkit.config import configs

# This function is now async, as required to contain async operations
async def sql_agent_page(current_llm: BaseLLM):
    """
    Renders the SQL Agent page in the Streamlit application.
    """
    st.header("SQL Query Generator")
    st.write("Convert natural language questions into SQL queries using an LLM.")

    # Display warning if no LLM is currently selected or initialized
    if not current_llm:
        st.warning("Please select and initialize an LLM provider in the sidebar settings to use the SQL Agent.")
        return

    # Initialize SchemaManager using st.cache_resource.
    # SchemaManager is hashable and its path is a string, so this is safe.
    @st.cache_resource
    def get_schema_manager_cached_instance(): # Renamed function for clarity
        # Accessing schema_storage_path using the user's preferred method
        return SchemaManager(configs.get('sql_agent_settings').get('schema_storage_path'))

    schema_manager = get_schema_manager_cached_instance()

    # --- SQLAgent Initialization managed directly in session_state ---
    # Initialize SQLAgent only if it doesn't exist in session_state OR
    # if the underlying LLM (by its model name) has changed.
    # This ensures the SQLAgent instance always uses the currently selected LLM.
    if "sql_agent_instance" not in st.session_state or \
       st.session_state.get("last_llm_model_for_sql_agent") != current_llm.model_name:
        st.session_state.sql_agent_instance = SQLAgent(current_llm)
        st.session_state.last_llm_model_for_sql_agent = current_llm.model_name
    
    # Get the SQLAgent instance from session state
    sql_agent: SQLAgent = st.session_state.sql_agent_instance

    # --- Schema Management Section ---
    st.subheader("Manage Database Schemas")
    with st.expander("Add/View/Delete Schemas"):
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("##### Add/Update Schema")
            new_schema_name = st.text_input("New Schema Name:", key="new_schema_name_input")
            new_schema_definition = st.text_area(
                "Schema Definition (e.g., CREATE TABLE statements or descriptive text):",
                height=200, key="new_schema_definition_input"
            )
            if st.button("Save Schema", key="save_schema_button"):
                if new_schema_name and new_schema_definition:
                    # Add the new schema using the SchemaManager
                    if schema_manager.add_schema(new_schema_name, new_schema_definition):
                        st.success(f"Schema '{new_schema_name}' saved successfully!")
                        st.session_state.schema_refresh_trigger = True # Trigger rerun to update dropdowns
                    else:
                        st.info(f"Schema '{new_schema_name}' already exists with the same definition. No update needed.")
                else:
                    st.warning("Please provide both a schema name and definition to save.")

        with col2:
            st.markdown("##### Existing Schemas")
            all_schema_names = schema_manager.get_all_schema_names()
            if not all_schema_names:
                st.info("No schemas defined yet. Add one on the left!")
            else:
                selected_schema_to_view = st.selectbox(
                    "Select Schema to View/Delete:",
                    options=[""] + all_schema_names, # Add an empty option for no selection
                    key="select_schema_to_view"
                )
                if selected_schema_to_view:
                    # Display the selected schema's definition
                    st.code(schema_manager.get_schema(selected_schema_to_view), language="sql")
                    if st.button(f"Delete '{selected_schema_to_view}'", key="delete_schema_button"):
                        # Delete the selected schema
                        if schema_manager.delete_schema(selected_schema_to_view):
                            st.success(f"Schema '{selected_schema_to_view}' deleted.")
                            st.session_state.schema_refresh_trigger = True # Trigger rerun
                        else:
                            st.error("Error deleting schema. Schema might not exist.")

    st.markdown("---")

    # --- SQL Query Generation Section ---
    st.subheader("Generate SQL Query")

    available_schemas = schema_manager.get_all_schema_names()
    if not available_schemas:
        st.warning("Please add at least one database schema in the 'Manage Database Schemas' section above to generate queries.")
        # Do not return here, so user can still see the warning and add a schema.
        # The generation section simply won't be usable yet.

    selected_query_schema_name = st.selectbox(
        "Select Database Schema:",
        options=available_schemas,
        key="selected_query_schema_name",
        disabled=not available_schemas # Disable if no schemas exist
    )
    # Get the definition for the selected schema
    selected_schema_definition = schema_manager.get_schema(selected_query_schema_name) if selected_query_schema_name else None

    natural_language_question = st.text_input(
        "Enter your question in natural language:",
        placeholder="e.g., Show me all customers from New York who joined last year.",
        key="nl_question_sql_agent",
        disabled=not selected_schema_definition # Disable if no schema is selected
    )

    # Session state for SQL Agent's chat history
    if "sql_agent_messages" not in st.session_state:
        st.session_state.sql_agent_messages = []

    # Display historical messages for the SQL Agent
    for message in st.session_state.sql_agent_messages:
        with st.chat_message(message["role"]):
            if message["type"] == "question":
                st.markdown(f"**Question:** {message['content']}")
                st.markdown(f"**Schema Used:** `{message['schema']}`")
            elif message["type"] == "sql_query":
                st.markdown(f"**Generated SQL:**")
                st.code(message["content"], language="sql")
            elif message["type"] == "error":
                st.error(f"**Error:** {message['content']}")


    # Button to trigger SQL generation
    if st.button("Generate SQL", key="generate_sql_button", disabled=not (natural_language_question and selected_schema_definition)):
        if natural_language_question and selected_schema_definition:
            # Add user's question to the agent's chat history
            st.session_state.sql_agent_messages.append({
                "role": "user",
                "type": "question",
                "content": natural_language_question,
                "schema": selected_query_schema_name
            })
            with st.chat_message("assistant"):
                message_placeholder = st.empty() # Placeholder for streaming output
                full_sql_response = ""
                try:
                    # Stream the SQL query generation
                    async for chunk in sql_agent.stream_sql_query(natural_language_question, selected_schema_definition):
                        full_sql_response += chunk
                        # Show raw streaming output in a code block with blinking cursor
                        message_placeholder.markdown(f"Generating... \n```sql\n{full_sql_response}▌\n```")

                    # After streaming is complete, extract and display the final SQL
                    final_extracted_sql = sql_agent._extract_sql_from_response(full_sql_response)
                    message_placeholder.markdown(f"**Generated SQL:**")
                    message_placeholder.code(final_extracted_sql, language="sql")

                    # Add the generated SQL to the agent's chat history
                    st.session_state.sql_agent_messages.append({
                        "role": "assistant",
                        "type": "sql_query",
                        "content": final_extracted_sql
                    })

                except Exception as e:
                    st.error(f"Error generating SQL: {e}")
                    # Add error message to chat history
                    st.session_state.sql_agent_messages.append({
                        "role": "assistant",
                        "type": "error",
                        "content": f"An error occurred: {e}"
                    })
        else:
            st.warning("Please ensure a natural language question is entered and a database schema is selected.")

    # A simple trigger to force Streamlit to rerun the script,
    # useful for updating selectboxes after adding/deleting schemas.
    if "schema_refresh_trigger" in st.session_state and st.session_state.schema_refresh_trigger:
        st.session_state.schema_refresh_trigger = False
        st.rerun()