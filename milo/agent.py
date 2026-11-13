import json
from google.genai import types

def run_agent_loop(chat, user_input: str, tools_map: dict, max_iterations: int = 6):
    """
    Executes a multi-step ReAct agent loop.
    Yields structured events so you can stream steps to a terminal, UI, or mobile backend.
    """
    # Send the initial user message to the chat session
    try:
        response = chat.send_message(user_input)
    except Exception as exc:
        yield {"type": "error", "iteration": 0, "content": str(exc)}
        return

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        
        # If the model didn't request any tool calls, it's returning the final text answer
        if not response.function_calls:
            yield {
                "type": "final_answer",
                "iteration": iteration,
                "content": response.text or "(no text response)"
            }
            break
            
        # Process each tool call requested by the model
        for call in response.function_calls:
            tool_name = call.name
            tool_args = call.args
            
            yield {
                "type": "tool_call",
                "iteration": iteration,
                "data": {"tool": tool_name, "args": tool_args}
            }
            
            # Look up and execute the tool
            if tool_name in tools_map:
                try:
                    tool_func = tools_map[tool_name]
                    result = tool_func(**tool_args)
                    observation = str(result)
                except Exception as exc:
                    observation = f"Error executing {tool_name}: {exc}"
            else:
                observation = f"Error: Tool '{tool_name}' not found in registry."
                
            yield {
                "type": "tool_result",
                "iteration": iteration,
                "data": {"tool": tool_name, "observation": observation}
            }
            
            # Feed the tool observation back into the chat session
            try:
                response = chat.send_message(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": observation}
                    )
                )
            except Exception as exc:
                yield {"type": "error", "iteration": iteration, "content": f"Failed to send tool response: {exc}"}
                return
    else:
        yield {
            "type": "error",
            "iteration": iteration,
            "content": "Max iterations reached without finalizing response."
        }