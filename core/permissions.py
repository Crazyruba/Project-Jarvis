class PermissionManager:
    """
    Confirms sensitive actions (send/delete/post/create) before they run.
    In Phase 3 it asks via text input. Later (voice phase) we just swap
    the `ask` function for a spoken yes/no — the rest stays the same.
    """

    def __init__(self, confirm_func=None):
        # Default confirmation = terminal input
        self.confirm_func = confirm_func or self._default_confirm

    def _default_confirm(self, message: str) -> bool:
        answer = input(f"\n⚠️  {message} (yes/no): ").strip().lower()
        return answer in {"ja", "jawel", "doe maar", "ok", "oke", "oké", "yes", "y"}

    def request(self, tool_name: str, args: dict) -> bool:
        """Vraag de eigenaar om een gevoelige actie goed te keuren."""
        pretty_args = ", ".join(f"{k}={v}" for k, v in args.items())
        message = f"JARVIS wil '{tool_name}' uitvoeren ({pretty_args}). Toestaan?"
        return self.confirm_func(message)