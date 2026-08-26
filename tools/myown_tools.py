def flatten(text:str) -> str:
    return "\n".join(line.lstrip() for line in text.splitlines())