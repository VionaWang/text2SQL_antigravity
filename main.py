import dotenv
import argparse
from agent import build_graph

dotenv.load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Text2SQL Agent CLI")
    parser.add_argument("--verbose", action="store_true", help="Print debug info")
    args = parser.parse_args()

    graph = build_graph()
    
    print("Welcome to the Text2SQL Agent! (Type 'quit' to exit)")
    print("Dataset: bigquery-public-data.thelook_ecommerce")
    
    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() in ["quit", "exit"]:
                break
            
            # Initial State
            initial_state = {
                "user_query": user_input,
                "messages": [("user", user_input)],
                "retry_count": 0,
                "error": None,
                "query_result": []
            }
            
            final_response = ""
            print("Agent: Thinking...", end="", flush=True)
            
            for event in graph.stream(initial_state):
                for node_name, state_update in event.items():
                    if state_update is None:
                        continue
                        
                    if args.verbose:
                        print(f"\n\n[Node: {node_name}]")
                        if "candidate_sql" in state_update:
                            print(f"SQL: {state_update['candidate_sql']}")
                        if "error" in state_update and state_update["error"]:
                            print(f"Error: {state_update['error']}")
                    
                    if "final_answer" in state_update:
                        final_response = state_update["final_answer"]
            
            print("\n\nAgent Response:")
            print(final_response)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()
