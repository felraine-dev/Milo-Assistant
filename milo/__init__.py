"""Milo, a local Gemini assistant with discoverable tools."""

__all__ = ["load_tools"]


def __getattr__(name: str):
    if name == "load_tools":
        from milo.registry import load_tools

        return load_tools
    raise AttributeError(name)
