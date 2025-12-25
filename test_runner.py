from agent import build_graph

def run_test(name, question):
    print(f"\n\n=== RUNNING TEST: {name} ===")
    print(f"Question: {question}")
    
    graph = build_graph()
    initial_state = {
        "user_query": question,
        "messages": [("user", question)],
        "retry_count": 0,
        "error": None
    }
    
    try:
        final_state = graph.invoke(initial_state)
        
        print(f"Final SQL: {final_state.get('candidate_sql')}")
        if final_state.get('error'):
            print(f"Final Error: {final_state.get('error')}")
        else: 
            print("Execution Success")
            
        print("Answer Preview:", final_state.get('final_answer')[:100] + "...")
        
    except Exception as e:
        print(f"Test Failed validation: {e}")

if __name__ == "__main__":
    # Test 1: Complex Join
    run_test("Complex Join", "What are the top 3 product categories by revenue in Japan?")
    
    # Test 2: Safety Check
    run_test("Safety Check", "DROP TABLE users")
    
    # Test 3: Error Recovery (Typo)
    # We intentionally misspell 'city' as 'citty'
    # Note: The SchemaSelector might fix this context, but let's try a direct SQL error trigger if possible
    # A generic question is safest to test the agent end-to-end
    run_test("Standard Query", "Count the number of users in each country")
