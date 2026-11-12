import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from tools.system_tools import get_system_health, check_git_status, get_git_history

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Configure Milo's personality and Skill 2 toolkit
config = types.GenerateContentConfig(
    system_instruction=(
        "You are Milo, a sharp, concise personal developer assistant. "
        "Use your tools to inspect system metrics or check git repositories when asked."
    ),
    tools=[get_system_health, check_git_status, get_git_history],
    temperature=0.2,
)

# Initialize a stateful chat session (handles automatic function calling)
chat = client.chats.create(model="gemini-3.5-flash-lite", config=config)

def run_cli():
    print("Milo Online. Type 'exit' to quit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        
        response = chat.send_message(user_input)
        print(f"\nMilo: {response.text}\n")

if __name__ == "__main__":
    run_cli()