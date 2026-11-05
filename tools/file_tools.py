import os


def read_file(path: str):
    """Read and return the contents of a text file."""
    if not os.path.exists(path):
        return f"Bestand niet gevonden: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Keep responses sane for large files
        if len(content) > 4000:
            return content[:4000] + "\n…[ingekort]"
        return content
    except Exception as e:
        return f"Ik kon het bestand niet lezen: {e}"


def write_file(path: str, content: str):
    """Write text content to a file (creates or overwrites)."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Opgeslagen in {path}."
    except Exception as e:
        return f"Ik kon niet schrijven: {e}"


def search_files(directory: str, keyword: str):
    """Search a directory for filenames containing a keyword."""
    if not os.path.isdir(directory):
        return f"Map niet gevonden: {directory}"
    matches = []
    for root, _, files in os.walk(directory):
        for name in files:
            if keyword.lower() in name.lower():
                matches.append(os.path.join(root, name))
    if not matches:
        return f"Geen bestanden met '{keyword}' in {directory}."
    return "Gevonden:\n" + "\n".join(matches[:20])


def register_file_tools(registry):
    registry.register(
        name="read_file",
        func=read_file,
        description="Lees de tekstinhoud van een bestand.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Volledig pad naar het bestand."}
            },
            "required": ["path"],
        },
    )

    registry.register(
        name="write_file",
        func=write_file,
        description="Schrijf tekst naar een bestand (maakt het aan of overschrijft het).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Volledig pad naar het bestand."},
                "content": {"type": "string", "description": "De tekst die weggeschreven wordt."},
            },
            "required": ["path", "content"],
        },
        sensitive=True,   # 🔐 writing changes disk -> confirm first
    )

    registry.register(
        name="search_files",
        func=search_files,
        description="Zoek in een map naar bestanden met een woord in de naam.",
        parameters={
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "De map waarin gezocht wordt."},
                "keyword": {"type": "string", "description": "Woord om in bestandsnamen te zoeken."},
            },
            "required": ["directory", "keyword"],
        },
    )