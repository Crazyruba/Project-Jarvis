from google.genai import types
class ToolRegistry:
    """Holds tools, exposes schemas to Gemini, and enforces permissions."""

    def __init__(self, permission_manager=None):
        self._tools = {}
        self.permissions = permission_manager

    def register(self, name, func, description, parameters=None, sensitive=False):
        if parameters is None:
            parameters = {"type": "object", "properties": {}}

        self._tools[name] = {
            "func": func,
            "sensitive": sensitive,
            "declaration": types.FunctionDeclaration(
                name=name,
                description=description,
                parameters=parameters,
            ),
        }

    def get_schemas(self):
        return [tool["declaration"] for tool in self._tools.values()]

    def execute(self, name, args=None):
        if name not in self._tools:
            return f"Error: unknown tool '{name}'"

        args = args or {}
        tool = self._tools[name]

        if tool["sensitive"] and self.permissions:
            approved = self.permissions.request(name, args)
            if not approved:
                return f"Actie '{name}' is geannuleerd."

        try:
            return tool["func"](**args)
        except Exception as e:
            print(f"Tool error in '{name}': {e}")
            return f"Tool '{name}' error: {e}"