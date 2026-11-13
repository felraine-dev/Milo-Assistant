import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from milo.registry import load_tools
from milo.agent import run_agent_loop

SYSTEM_INSTRUCTION = (
    "You are Milo, a sharp, concise personal developer assistant. "
    "Always refer to yourself in the first person ('I', 'my') as Milo, "
    "and never refer to yourself in the third person as 'your assistant'. "
    "Use tools for system health, disk, development processes, git status, "
    "git history, diff summaries, conventional commit drafts, and workspace setup. "
    "draft_conventional_commit only drafts a message. Do not claim that you committed, "
    "pushed, or installed packages unless a tool result says that command finished. "
    "prepare_workspace and launch_workspace ask for confirmation in the terminal. "
    "If a tool result says Cancelled, stop and do not retry it. "
    "Do not invent tool results."
)


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Missing GEMINI_API_KEY. Add it to .env or the environment.")

    tools = load_tools()
    tools_map = {fn.__name__: fn for fn in tools}
    
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=tools,
        temperature=0.2,
    )
    chat = client.chats.create(model="gemini-3.5-flash-lite", config=config)

    print("Milo Online. Type 'exit' to quit.")
    for fn in tools:
        print(f"  - {fn.__name__} [{getattr(fn, '_milo_risk', 'low')}]")
    print()

    while True:
        try:
            user_input = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.strip().lower() in {"exit", "quit"}:
            break
        if not user_input.strip():
            continue

        print("\nMilo: ", end="", flush=True)
        
        for event in run_agent_loop(chat, user_input, tools_map):
            etype = event["type"]
            data = event.get("data", {})
            
            if etype == "tool_call":
                print(f"\n[Thinking: Calling `{data.get('tool')}` with {data.get('args')}]")
            elif etype == "tool_result":
                pass
            elif etype == "final_answer":
                print(f"{event['content']}\n")
            elif etype == "error":
                print(f"\n[Error: {event['content']}]\n")


if __name__ == "__main__":
    main()