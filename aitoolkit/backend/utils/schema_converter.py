# aitoolkit/utils/schema_converter.py
import json
import re
from typing import Dict, List, Union, Optional

class SchemaConverter:
    """
    Utility class to convert between different schema formats:
    - Structured JSON format (with descriptions and metadata)
    - DDL format (CREATE TABLE statements)
    - Simple table format
    """
    
    @staticmethod
    def ddl_to_structured(ddl_text: str, database_name: str = None, sql_language: str = "SQL", 
                         database_description: str = "") -> Dict:
        """
        Converts DDL text to structured schema format.
        
        Args:
            ddl_text: CREATE TABLE statements
            database_name: Name for the database (auto-generated if None)
            sql_language: SQL dialect (MySQL, PostgreSQL, etc.)
            database_description: Description of the database
            
        Returns:
            Structured schema dictionary
        """
        # Extract database name from DDL comments or use default
        if not database_name:
            db_match = re.search(r'--\s*Database:\s*(.+)', ddl_text, re.IGNORECASE)
            database_name = db_match.group(1).strip() if db_match else "Converted_Database"
        
        # Extract SQL language from comments if not provided
        lang_match = re.search(r'--\s*Language:\s*(.+)', ddl_text, re.IGNORECASE)
        if lang_match:
            sql_language = lang_match.group(1).strip()
        
        # Extract database description from comments if not provided
        if not database_description:
            desc_match = re.search(r'--\s*Description:\s*(.+)', ddl_text, re.IGNORECASE)
            database_description = desc_match.group(1).strip() if desc_match else ""
        
        tables = []
        
        # Find all CREATE TABLE statements
        table_pattern = r'CREATE TABLE\s+`?(\w+)`?\s*\((.*?)\)\s*;'
        table_matches = re.findall(table_pattern, ddl_text, re.DOTALL | re.IGNORECASE)
        
        for table_name, columns_str in table_matches:
            # Look for table description in comments before the CREATE TABLE
            table_desc_pattern = r'--\s*Table:\s*{re.escape(table_name)}\s*-\s*(.+?)(?:\n|$)'
            table_desc_match = re.search(table_desc_pattern, ddl_text, re.IGNORECASE)
            table_description = table_desc_match.group(1).strip() if table_desc_match else ""
            
            columns = []
            
            # Parse columns - this is a simplified parser
            column_lines = [line.strip() for line in columns_str.split(',')]
            
            for line in column_lines:
                if not line or line.upper().startswith('CONSTRAINT') or line.upper().startswith('INDEX'):
                    continue
                
                # Extract column info using regex
                col_match = re.match(r'`?(\w+)`?\s+(\w+(?:\([^)]+\))?)\s*(.*)', line, re.IGNORECASE)
                if col_match:
                    col_name = col_match.group(1)
                    col_type = col_match.group(2)
                    col_constraints = col_match.group(3).upper()
                    
                    is_pk = 'PRIMARY KEY' in col_constraints or 'PK' in col_constraints
                    
                    columns.append({
                        "column_name": col_name,
                        "type": col_type,
                        "is_pk": is_pk,
                        "description": f"Column {col_name} of type {col_type}"
                    })
            
            tables.append({
                "table_name": table_name,
                "description": table_description,
                "columns": columns
            })
        
        return {
            "database_name": database_name,
            "sql_language": sql_language,
            "description": database_description,
            "tables": tables
        }
    
    @staticmethod
    def structured_to_ddl(structured_schema: Dict) -> str:
        """
        Converts structured schema format to DDL text.
        
        Args:
            structured_schema: Dictionary with database, tables, and columns info
            
        Returns:
            DDL text with CREATE TABLE statements
        """
        ddl_parts = []
        
        # Add header comments
        ddl_parts.append(f"-- Database: {structured_schema.get('database_name', 'Unknown')}")
        ddl_parts.append(f"-- Language: {structured_schema.get('sql_language', 'SQL')}")
        
        if structured_schema.get('description'):
            ddl_parts.append(f"-- Description: {structured_schema['description']}")
        
        ddl_parts.append("")
        
        # Process each table
        for table in structured_schema.get('tables', []):
            table_name = table.get('table_name', 'unknown_table')
            table_desc = table.get('description', '')
            
            # Add table comment
            if table_desc:
                ddl_parts.append(f"-- Table: {table_name} - {table_desc}")
            
            # Build CREATE TABLE statement
            ddl_parts.append(f"CREATE TABLE {table_name} (")
            
            columns = table.get('columns', [])
            column_definitions = []
            
            for col in columns:
                col_name = col.get('column_name', 'unknown_col')
                col_type = col.get('type', 'VARCHAR(255)')
                is_pk = col.get('is_pk', False)
                
                col_def = f"    {col_name} {col_type}"
                if is_pk:
                    col_def += " PRIMARY KEY"
                
                column_definitions.append(col_def)
            
            ddl_parts.append(",\n".join(column_definitions))
            ddl_parts.append(");")
            ddl_parts.append("")
        
        return "\n".join(ddl_parts)
    
    @staticmethod
    def validate_structured_schema(schema: Dict) -> List[str]:
        """
        Validates a structured schema and returns a list of issues found.
        
        Args:
            schema: Dictionary to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        issues = []
        
        # Check required top-level fields
        if 'database_name' not in schema:
            issues.append("Missing required field: database_name")
        
        if 'tables' not in schema:
            issues.append("Missing required field: tables")
        elif not isinstance(schema['tables'], list):
            issues.append("Field 'tables' must be a list")
        else:
            # Validate each table
            for i, table in enumerate(schema['tables']):
                if not isinstance(table, dict):
                    issues.append(f"Table {i+1}: must be a dictionary")
                    continue
                
                if 'table_name' not in table:
                    issues.append(f"Table {i+1}: missing required field 'table_name'")
                
                if 'columns' not in table:
                    issues.append(f"Table {i+1}: missing required field 'columns'")
                elif not isinstance(table['columns'], list):
                    issues.append(f"Table {i+1}: 'columns' must be a list")
                else:
                    # Validate each column
                    table_name = table.get('table_name', f'Table_{i+1}')
                    for j, col in enumerate(table['columns']):
                        if not isinstance(col, dict):
                            issues.append(f"Table '{table_name}', Column {j+1}: must be a dictionary")
                            continue
                        
                        if 'column_name' not in col:
                            issues.append(f"Table '{table_name}', Column {j+1}: missing 'column_name'")
                        
                        if 'type' not in col:
                            issues.append(f"Table '{table_name}', Column {j+1}: missing 'type'")
        
        return issues
    
    @staticmethod
    def enhance_structured_schema(schema: Dict, add_sample_descriptions: bool = True) -> Dict:
        """
        Enhances a basic structured schema by adding missing fields and descriptions.
        
        Args:
            schema: Basic structured schema
            add_sample_descriptions: Whether to add sample descriptions for missing ones
            
        Returns:
            Enhanced schema with additional metadata
        """
        enhanced = schema.copy()
        
        # Add missing top-level fields
        if 'sql_language' not in enhanced:
            enhanced['sql_language'] = 'SQL'
        
        if 'description' not in enhanced and add_sample_descriptions:
            enhanced['description'] = f"Database schema for {enhanced.get('database_name', 'Unknown')}"
        
        # Enhance tables
        for table in enhanced.get('tables', []):
            if 'description' not in table and add_sample_descriptions:
                table_name = table.get('table_name', 'Unknown')
                table['description'] = f"Data table for {table_name.lower().replace('_', ' ')}"
            
            # Enhance columns
            for col in table.get('columns', []):
                if 'is_pk' not in col:
                    col['is_pk'] = False
                
                if 'description' not in col and add_sample_descriptions:
                    col_name = col.get('column_name', 'unknown')
                    col_type = col.get('type', 'VARCHAR')
                    col['description'] = f"{col_name.replace('_', ' ').title()} field of type {col_type}"
        
        return enhanced
    
    @staticmethod
    def create_sample_ecommerce_schema() -> Dict:
        """
        Creates a sample e-commerce structured schema for testing.
        
        Returns:
            Complete structured schema example
        """
        return {
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
                            "is_pk": False,
                            "description": "Customer's first name."
                        },
                        {
                            "column_name": "last_name",
                            "type": "VARCHAR(50)",
                            "is_pk": False,
                            "description": "Customer's last name."
                        },
                        {
                            "column_name": "email",
                            "type": "VARCHAR(255)",
                            "is_pk": False,
                            "description": "Customer's email address for communication."
                        },
                        {
                            "column_name": "registration_date",
                            "type": "DATE",
                            "is_pk": False,
                            "description": "Date when the customer registered."
                        }
                    ]
                },
                {
                    "table_name": "Orders",
                    "description": "Contains order information and purchase details.",
                    "columns": [
                        {
                            "column_name": "order_id",
                            "type": "INTEGER",
                            "is_pk": True,
                            "description": "Unique identifier for each order."
                        },
                        {
                            "column_name": "customer_id",
                            "type": "INTEGER",
                            "is_pk": False,
                            "description": "Foreign key referencing the customer who placed the order."
                        },
                        {
                            "column_name": "order_date",
                            "type": "DATE",
                            "is_pk": False,
                            "description": "Date when the order was placed."
                        },
                        {
                            "column_name": "total_amount",
                            "type": "DECIMAL(10,2)",
                            "is_pk": False,
                            "description": "Total monetary value of the order."
                        },
                        {
                            "column_name": "status",
                            "type": "VARCHAR(20)",
                            "is_pk": False,
                            "description": "Current status of the order (pending, shipped, delivered, etc.)."
                        }
                    ]
                },
                {
                    "table_name": "Products",
                    "description": "Product catalog with details and pricing.",
                    "columns": [
                        {
                            "column_name": "product_id",
                            "type": "INTEGER",
                            "is_pk": True,
                            "description": "Unique identifier for each product."
                        },
                        {
                            "column_name": "product_name",
                            "type": "VARCHAR(255)",
                            "is_pk": False,
                            "description": "Name of the product."
                        },
                        {
                            "column_name": "category",
                            "type": "VARCHAR(100)",
                            "is_pk": False,
                            "description": "Product category classification."
                        },
                        {
                            "column_name": "price",
                            "type": "DECIMAL(8,2)",
                            "is_pk": False,
                            "description": "Current selling price of the product."
                        },
                        {
                            "column_name": "stock_quantity",
                            "type": "INTEGER",
                            "is_pk": False,
                            "description": "Current available inventory count."
                        }
                    ]
                }
            ]
        }

# Example usage functions
def convert_ddl_file_to_structured(ddl_file_path: str, output_file_path: str = None) -> Dict:
    """
    Reads a DDL file and converts it to structured format.
    
    Args:
        ddl_file_path: Path to the DDL file
        output_file_path: Optional path to save the structured schema
        
    Returns:
        Structured schema dictionary
    """
    with open(ddl_file_path, 'r', encoding='utf-8') as f:
        ddl_content = f.read()
    
    structured = SchemaConverter.ddl_to_structured(ddl_content)
    
    if output_file_path:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(structured, f, indent=2)
    
    return structured

def convert_structured_file_to_ddl(structured_file_path: str, output_file_path: str = None) -> str:
    """
    Reads a structured schema file and converts it to DDL format.
    
    Args:
        structured_file_path: Path to the JSON structured schema file
        output_file_path: Optional path to save the DDL
        
    Returns:
        DDL text
    """
    with open(structured_file_path, 'r', encoding='utf-8') as f:
        structured = json.load(f)
    
    ddl = SchemaConverter.structured_to_ddl(structured)
    
    if output_file_path:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(ddl)
    
    return ddl