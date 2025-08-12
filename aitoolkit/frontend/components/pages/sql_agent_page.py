# aitoolkit/frontend/components/pages/sql_agent_page.py
import streamlit as st
import asyncio
import logging
import json

from aitoolkit.backend.llm import BaseLLM, LLM_REGISTRY, EMBEDDING_LLM_REGISTRY, EmbeddingLLM
from aitoolkit.backend.db import SchemaManager
from aitoolkit.backend.agents import SQLAgent
from aitoolkit.config import configs
from typing import Optional

log = logging.getLogger(__name__)

async def sql_agent_page(current_llm: BaseLLM):
    """
    Renders the SQL Agent page in the Streamlit application.
    Now supports both structured JSON schemas and DDL format.
    """
    st.header("SQL Query Generator")
    st.write("Convert natural language questions into SQL queries using an LLM.")

    # Display warning if no chat LLM is currently selected or initialized
    if not current_llm:
        st.warning("Please select and initialize a **Chat LLM** provider in the sidebar settings to use the SQL Agent.")
        return

    # --- Initialize Embedding LLM for SchemaManager ---
    embedding_llm_instance: Optional[EmbeddingLLM] = None
    
    # Get embedding provider settings from config
    embedding_providers = configs.get('embedding_settings', {}).get('available_providers', [])
    default_embedding_provider = configs.get('embedding_settings').get('default_provider')
    
    # Allow user to select embedding provider in the sidebar if desired, or keep it fixed
    selected_embedding_provider = st.sidebar.selectbox(
        "Select Embedding Provider:",
        options=embedding_providers,
        index=embedding_providers.index(default_embedding_provider) if default_embedding_provider in embedding_providers else 0,
        key="embedding_provider_selection"
    )

    # Get the default model name for the selected embedding provider
    embedding_model_key = f"{selected_embedding_provider.lower().replace(' ', '_')}_default_embedding_model"
    embedding_model_name = configs.get('embedding_settings').get(embedding_model_key)

    if selected_embedding_provider:
        embedding_llm_class = EMBEDDING_LLM_REGISTRY.get(selected_embedding_provider)
        if embedding_llm_class:
            try:
                embedding_llm_instance = embedding_llm_class(model_name=embedding_model_name)
            except ImportError as e:
                st.error(f"Required library for {selected_embedding_provider} embeddings missing: {e}. Please install it.")
                log.error(f"Embedding LLM initialization failed: {e}")
                return
            except ValueError as e:
                st.warning(f"Embedding LLM API key/setup error for {selected_embedding_provider}: {e}. Schema management and SQL agent might not work correctly.")
                log.warning(f"Embedding LLM API key/setup warning: {e}")
                if "API key is not set" in str(e) or "Failed to generate embedding" in str(e):
                    # If API key is critical, stop here
                    return
        else:
            st.error(f"Unknown embedding provider: {selected_embedding_provider}. Please check your configuration.")
            return
    else:
        st.warning("No embedding provider selected. Schema management cannot function.")
        return

    st.sidebar.info(f"Embeddings: {embedding_llm_instance.model_name} from {embedding_llm_instance.get_model_info()['provider']}")

    # Initialize SchemaManager using st.cache_resource.
    @st.cache_resource
    def get_schema_manager_cached_instance(_embed_llm_inst: EmbeddingLLM):
        vector_db_path = configs.get('rag_agent_settings').get('persist_directory')
        schema_path = configs.get('sql_agent_settings').get('schema_storage_path')
        return SchemaManager(schema_path, vector_db_path, _embed_llm_inst)

    schema_manager = get_schema_manager_cached_instance(embedding_llm_instance)

    # --- SQLAgent Initialization managed directly in session_state ---
    if "sql_agent_instance" not in st.session_state or \
       st.session_state.get("last_chat_llm_model_for_sql_agent") != current_llm.model_name or \
       st.session_state.get("last_embedding_model_for_sql_agent") != embedding_llm_instance.model_name:
        
        log.info(f"Re-initializing SQLAgent. Chat LLM: {current_llm.model_name}, Embedding LLM: {embedding_llm_instance.model_name}")
        st.session_state.sql_agent_instance = SQLAgent(current_llm, embedding_llm_instance, schema_manager)
        st.session_state.last_chat_llm_model_for_sql_agent = current_llm.model_name
        st.session_state.last_embedding_model_for_sql_agent = embedding_llm_instance.model_name
    
    sql_agent: SQLAgent = st.session_state.sql_agent_instance

    # --- Schema Management Section ---
    st.subheader("Manage Database Schemas")
    
    # Add tabs for different schema input methods
    tab1, tab2, tab3 = st.tabs(["📝 Add Schema", "📊 View Schemas", "🗑️ Delete Schema"])
    
    with tab1:
        st.markdown("##### Add/Update Database Schema")
        
        # Schema input method selection
        input_method = st.radio(
            "Choose input method:",
            ["Structured JSON Format", "SQL DDL Format", "Auto-detect"],
            key="schema_input_method"
        )
        
        if input_method == "Structured JSON Format":
            st.info("💡 **Structured Format**: Provide schema as a JSON object with database info, tables, and columns with descriptions.")
            with st.expander("📋 View Example Structured Schema", expanded=False):
                example_schema = {
                    "database_name": "ECommerceAnalyticsDB",
                    "sql_language": "MySQL",
                    "description": "A comprehensive database for tracking e-commerce operations, customer behavior, and sales analytics.",
                    "tables": [
                        {
                            "table_name": "Customers",
                            "description": "Stores information about registered customers.",
                            "columns": [
                                {
                                    "column_name": "customer_id",
                                    "type": "INTEGER",
                                    "is_pk": True,
                                    "description": "Unique identifier for each customer."
                                },
                                {
                                    "column_name": "first_name", 
                                    "type": "VARCHAR(50)",
                                    "description": "Customer's first name."
                                },
                                {
                                    "column_name": "email",
                                    "type": "VARCHAR(255)",
                                    "description": "Customer's email address."
                                }
                            ]
                        }
                    ]
                }
                st.json(example_schema)
        
        elif input_method == "SQL DDL Format":
            st.info("💡 **DDL Format**: Provide schema as CREATE TABLE statements.")
            with st.expander("📋 View Example DDL Schema", expanded=False):
                example_ddl = """CREATE TABLE Customers (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(50),
    email VARCHAR(255)
);

CREATE TABLE Orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date DATE,
    total_amount DECIMAL(10,2)
);"""
                st.code(example_ddl, language="sql")
        
        else:  # Auto-detect
            st.info("💡 **Auto-detect**: Paste your schema and the system will automatically detect if it's JSON or DDL format.")
        
        # Schema input
        col1, col2 = st.columns([2, 1])
        
        with col1:
            new_schema_definition = st.text_area(
                "Schema Definition:",
                height=300,
                key="new_schema_definition_input",
                placeholder="Paste your schema here (JSON or DDL format)..."
            )
        
        with col2:
            # Manual schema name input (optional for structured format)
            manual_schema_name = st.text_input(
                "Schema Name (optional):",
                key="manual_schema_name_input",
                help="Leave empty for auto-detection from schema content"
            )
            
            if st.button("💾 Save Schema", key="save_schema_button", type="primary"):
                if new_schema_definition.strip():
                    try:
                        with st.spinner("Processing schema and generating embeddings..."):
                            if manual_schema_name.strip():
                                # Use manual name with the provided definition
                                if input_method == "Structured JSON Format":
                                    try:
                                        schema_dict = json.loads(new_schema_definition)
                                        success = schema_manager.add_schema(manual_schema_name, schema_dict)
                                    except json.JSONDecodeError as e:
                                        st.error(f"Invalid JSON format: {e}")
                                        success = False
                                else:
                                    success = schema_manager.add_schema(manual_schema_name, new_schema_definition)
                                
                                if success:
                                    st.success(f"✅ Schema '{manual_schema_name}' saved successfully!")
                                else:
                                    st.info(f"ℹ️ Schema '{manual_schema_name}' already exists with the same definition.")
                            else:
                                # Auto-detect and extract name
                                schema_name = schema_manager.add_schema_from_text(new_schema_definition)
                                if schema_name:
                                    st.success(f"✅ Schema '{schema_name}' saved successfully!")
                                else:
                                    st.error("❌ Failed to save schema. Please check the format.")
                            
                            st.session_state.schema_refresh_trigger = True
                    except Exception as e:
                        st.error(f"❌ Error saving schema: {e}")
                        log.error(f"Schema save error: {e}")
                else:
                    st.warning("⚠️ Please provide a schema definition.")

    with tab2:
        st.markdown("##### View Existing Schemas")
        all_schema_names = schema_manager.get_all_schema_names()
        
        if not all_schema_names:
            st.info("📋 No schemas defined yet. Add one in the 'Add Schema' tab!")
        else:
            selected_schema_to_view = st.selectbox(
                "Select Schema to View:",
                options=all_schema_names,
                key="select_schema_to_view"
            )
            
            if selected_schema_to_view:
                # Get schema info
                schema_info = schema_manager.get_schema_info(selected_schema_to_view)
                
                if schema_info:
                    # Display schema summary
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Schema Type", schema_info['type'].upper())
                    with col2:
                        st.metric("🗂️ Tables", schema_info['table_count'])
                    with col3:
                        if schema_info['type'] == 'structured':
                            st.metric("🗣️ SQL Language", schema_info.get('sql_language', 'SQL'))
                
                # Display schema content
                view_format = st.radio("View as:", ["DDL Format", "Raw Format"], horizontal=True, key="view_format")
                
                if view_format == "DDL Format":
                    ddl_content = schema_manager.get_schema_as_string(selected_schema_to_view)
                    st.code(ddl_content, language="sql")
                else:
                    raw_content = schema_manager.get_schema(selected_schema_to_view)
                    if isinstance(raw_content, dict):
                        st.json(raw_content)
                    else:
                        st.code(raw_content, language="sql")
                
                # Table details for structured schemas
                if schema_info and schema_info['type'] == 'structured' and 'tables' in schema_info:
                    st.markdown("##### 📋 Table Details")
                    for table in schema_info['tables']:
                        with st.expander(f"Table: {table['name']} ({table['column_count']} columns)"):
                            raw_schema = schema_manager.get_schema(selected_schema_to_view)
                            if isinstance(raw_schema, dict):
                                # Find the table in the raw schema
                                for t in raw_schema.get('tables', []):
                                    if t.get('table_name') == table['name']:
                                        if t.get('description'):
                                            st.markdown(f"**Description:** {t['description']}")
                                        
                                        columns = t.get('columns', [])
                                        if columns:
                                            st.markdown("**Columns:**")
                                            for col in columns:
                                                pk_indicator = " 🔑" if col.get('is_pk') else ""
                                                col_desc = f" - {col.get('description', '')}" if col.get('description') else ""
                                                st.markdown(f"- `{col.get('column_name')}` ({col.get('type')}){pk_indicator}{col_desc}")
                                        break

    with tab3:
        st.markdown("##### Delete Schema")
        all_schema_names = schema_manager.get_all_schema_names()
        
        if not all_schema_names:
            st.info("📋 No schemas to delete.")
        else:
            selected_schema_to_delete = st.selectbox(
                "Select Schema to Delete:",
                options=[""] + all_schema_names,
                key="select_schema_to_delete"
            )
            
            if selected_schema_to_delete:
                schema_info = schema_manager.get_schema_info(selected_schema_to_delete)
                if schema_info:
                    st.warning(f"⚠️ **Schema to delete:** {selected_schema_to_delete}")
                    st.write(f"📊 Type: {schema_info['type'].upper()}")
                    st.write(f"🗂️ Tables: {schema_info['table_count']}")
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button(f"🗑️ Delete '{selected_schema_to_delete}'", key="delete_schema_button", type="secondary"):
                            try:
                                if schema_manager.delete_schema(selected_schema_to_delete):
                                    st.success(f"✅ Schema '{selected_schema_to_delete}' deleted successfully!")
                                    st.session_state.schema_refresh_trigger = True
                                else:
                                    st.error("❌ Error deleting schema. Schema might not exist.")
                            except Exception as e:
                                st.error(f"❌ Error deleting schema: {e}")
                                log.error(f"Schema delete error: {e}")
                    with col2:
                        st.info("💡 This action cannot be undone!")

    st.markdown("---")

    # --- SQL Query Generation Section ---
    st.subheader("🔍 Generate SQL Query")

    available_schemas = schema_manager.get_all_schema_names()
    if not available_schemas:
        st.warning("⚠️ Please add at least one database schema in the 'Add Schema' tab above to generate queries.")
        return
    
    # Schema selection with info display
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_query_schema_name = st.selectbox(
            "Select Database Schema:",
            options=available_schemas,
            key="selected_query_schema_name"
        )
    
    with col2:
        if selected_query_schema_name:
            schema_info = schema_manager.get_schema_info(selected_query_schema_name)
            if schema_info:
                st.info(f"📊 {schema_info['type'].upper()} | 🗂️ {schema_info['table_count']} tables")
    
    # Natural language question input
    natural_language_question = st.text_input(
        "Enter your question in natural language:",
        placeholder="e.g., Show me all customers from New York who joined last year.",
        key="nl_question_sql_agent",
        disabled=not selected_query_schema_name
    )

    # Query generation button
    col1, col2 = st.columns([1, 4])
    with col1:
        generate_button = st.button(
            "🚀 Generate SQL", 
            key="generate_sql_button", 
            disabled=not (natural_language_question and selected_query_schema_name),
            type="primary"
        )

    # Chat-like interface for queries and responses
    if "sql_agent_messages" not in st.session_state:
        st.session_state.sql_agent_messages = []

    # Display conversation history
    for message in st.session_state.sql_agent_messages:
        with st.chat_message(message["role"]):
            if message["type"] == "question":
                st.markdown(f"**Question:** {message['content']}")
                st.markdown(f"**Schema Used:** `{message['schema']}`")
            elif message["type"] == "sql_query":
                st.markdown("**Generated SQL:**")
                st.code(message["content"], language="sql")
                
                # Add copy button for SQL
                if st.button(f"📋 Copy SQL", key=f"copy_sql_{len(st.session_state.sql_agent_messages)}"):
                    st.write("SQL copied to clipboard!")  # Note: actual clipboard copy would need JS
                    
            elif message["type"] == "error":
                st.error(f"**Error:** {message['content']}")

    # Handle query generation
    if generate_button:
        if natural_language_question and selected_query_schema_name:
            # Add user question to chat
            st.session_state.sql_agent_messages.append({
                "role": "user",
                "type": "question",
                "content": natural_language_question,
                "schema": selected_query_schema_name
            })
            
            # Generate response
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_sql_response = ""
                
                try:
                    # Show progress
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    status_text.text("🧠 Analyzing question...")
                    progress_bar.progress(25)
                    
                    # Stream the SQL generation
                    chunk_count = 0
                    async for chunk in sql_agent.stream_sql_query(natural_language_question, selected_query_schema_name):
                        full_sql_response += chunk
                        chunk_count += 1
                        
                        # Update progress
                        progress = min(25 + (chunk_count * 2), 90)
                        progress_bar.progress(progress)
                        status_text.text("✍️ Generating SQL...")
                        
                        # Show partial response
                        message_placeholder.markdown(f"**Generating SQL...**\n```sql\n{full_sql_response}▌\n```")

                    # Complete progress
                    progress_bar.progress(100)
                    status_text.text("✅ SQL generated!")
                    
                    # Extract and display final SQL
                    final_extracted_sql = sql_agent._extract_sql_from_response(full_sql_response)
                    
                    # Clear progress indicators
                    progress_bar.empty()
                    status_text.empty()
                    
                    if final_extracted_sql.startswith("Error:") or final_extracted_sql.startswith("N/A"):
                        message_placeholder.error(f"**Error:** {final_extracted_sql}")
                        st.session_state.sql_agent_messages.append({
                            "role": "assistant",
                            "type": "error",
                            "content": final_extracted_sql
                        })
                    else:
                        message_placeholder.markdown("**Generated SQL:**")
                        message_placeholder.code(final_extracted_sql, language="sql")
                        
                        st.session_state.sql_agent_messages.append({
                            "role": "assistant",
                            "type": "sql_query",
                            "content": final_extracted_sql
                        })

                except Exception as e:
                    log.error(f"Unexpected error during SQL generation: {e}")
                    error_msg = f"An unexpected error occurred during SQL generation: {e}"
                    message_placeholder.error(f"**Error:** {error_msg}")
                    st.session_state.sql_agent_messages.append({
                        "role": "assistant",
                        "type": "error",
                        "content": error_msg
                    })
        else:
            st.warning("⚠️ Please ensure a natural language question is entered and a database schema is selected.")

    # Clear conversation button
    if st.session_state.sql_agent_messages:
        if st.button("🗑️ Clear Conversation", key="clear_conversation"):
            st.session_state.sql_agent_messages = []
            st.rerun()

    # Handle schema refresh trigger
    if "schema_refresh_trigger" in st.session_state and st.session_state.schema_refresh_trigger:
        st.session_state.schema_refresh_trigger = False
        st.rerun()

    # --- Additional Features Section ---
    with st.expander("🛠️ Advanced Features", expanded=False):
        st.markdown("##### Schema Management Tips")
        st.markdown("""
        **Structured JSON Format Benefits:**
        - Rich column descriptions improve query accuracy
        - Primary key information helps with joins
        - Database-level context enhances understanding
        - Better semantic search with detailed metadata
        
        **DDL Format Benefits:**
        - Familiar SQL syntax
        - Direct copy-paste from existing schemas
        - Works with legacy database exports
        
        **Best Practices:**
        - Use descriptive table and column names
        - Include column descriptions when possible
        - Specify primary keys and relationships
        - Keep schema definitions up to date
        """)
        
        st.markdown("##### Query Tips")
        st.markdown("""
        - Be specific about time ranges (e.g., "last month", "2023")
        - Mention specific column names when known
        - Use business terms that match your schema descriptions
        - Ask for specific aggregations (COUNT, SUM, AVG, etc.)
        """)

# Example usage and additional helper functions
def display_schema_preview(schema_content, max_lines=10):
    """Helper function to display a preview of schema content"""
    if isinstance(schema_content, dict):
        preview = json.dumps(schema_content, indent=2)
    else:
        preview = str(schema_content)
    
    lines = preview.split('\n')
    if len(lines) <= max_lines:
        return preview
    else:
        return '\n'.join(lines[:max_lines]) + f'\n... ({len(lines) - max_lines} more lines)'