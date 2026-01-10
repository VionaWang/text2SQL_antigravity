# Token Usage Optimization for Text2SQL Agent

## Problem

The agent is exceeding the max token limit when generating SQL queries because it's passing too much context to the LLM:

1. **Full schema context** for all relevant tables (can be very large)
2. **All training examples** (grows over time)
3. **Long prompts** with detailed instructions

## Solutions Implemented

### 1. Limit Schema Context
- Only include essential column information
- Truncate long descriptions
- Limit number of tables passed to LLM

### 2. Limit Training Examples
- Reduce from unlimited to max 3 most recent examples
- Implement smarter example selection (most relevant)

### 3. Optimize Prompts
- Remove redundant instructions
- Use more concise language

## Files to Update

1. `schema_manager.py` - Add truncation for schema descriptions
2. `agent.py` - Limit training examples and schema tables
3. `prompts.py` - Shorten prompts
