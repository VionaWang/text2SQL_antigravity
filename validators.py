import re

class SQLSecurityError(Exception):
    """Raised when SQL contains forbidden keywords."""
    pass

def validate_sql_safety(sql: str) -> bool:
    """
    Checks if the SQL query is safe to execute.
    Enforces READ-ONLY access.
    """
    # Normalize
    sql_upper = sql.upper()
    
    # Forbidden keywords (DML/DDL that modifies data)
    forbidden_keywords = [
        "DROP ", "DELETE ", "INSERT ", "UPDATE ", "ALTER ", 
        "TRUNCATE ", "CREATE ", "GRANT ", "REVOKE "
    ]
    
    for kw in forbidden_keywords:
        if kw in sql_upper:
            # Allow "CREATE TEMP TABLE" or "CREATE OR REPLACE TEMP" if needed for complex CTEs?
            # For strict MVP, we stick to pure SELECT / WITH
            raise SQLSecurityError(f"Security Alert: Forbidden keyword '{kw.strip()}' detected.")
            
    # Must start with SELECT or WITH
    # Remove leading comments or whitespace
    clean_sql = re.sub(r'^\s*--.*?\n', '', sql_upper, flags=re.MULTILINE).strip()
    
    if not (clean_sql.startswith("SELECT") or clean_sql.startswith("WITH")):
        raise SQLSecurityError("Security Alert: Query must start with SELECT or WITH.")
        
    return True
