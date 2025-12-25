from google.cloud import aiplatform
import os
from langchain_google_vertexai import ChatVertexAI

def list_models():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or "viona-opendata-proj"
    # Common regions for Vertex AI
    regions = ["us-central1", "us-east4", "us-west1", "europe-west1", "asia-southeast1"]
    
    print(f"Checking models for Project: {project_id}")
    known_models = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash", 
        "gemini-1.5-pro",
        "gemini-1.0-pro", 
        "gemini-pro",
        "gemini-ultra",
        "text-bison",
        "chat-bison",
        "code-bison",
        "code-gecko",
        "text-unicorn"
    ]
    
    successes = []
    
    for location in regions:
        print(f"\n--- Checking Region: {location} ---")
        try:
            aiplatform.init(project=project_id, location=location)
            # Try to invoke
            for model_name in known_models:
                try:
                    print(f"  Probing {model_name}...", end=" ", flush=True)
                    llm = ChatVertexAI(model=model_name, location=location, project=project_id, max_retries=0)
                    # We set max_retries=0 to fail fast
                    llm.invoke("Hello")
                    print(f"✅ FOUND!")
                    successes.append(f"{location}: {model_name}")
                except Exception as e:
                    if "404" in str(e):
                        print("❌ 404", end=" ")
                    elif "403" in str(e):
                         print("❌ 403", end=" ")
                    else:
                        print(f"⚠️ {str(e)[:10]}...", end=" ")
                    print("")
        except Exception as e:
            print(f"  Failed to init region: {e}")

    print("\n\n=== AVAILABLE MODELS ===")
    if successes:
        for s in successes:
            print(f" - {s}")
    else:
        print("No models found.")

if __name__ == "__main__":
    list_models()
