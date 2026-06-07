def panel(title: str, *lines: str) -> str:
    body = "\n".join(line for line in lines if line is not None)
    if body:
        return f"{title}\n{'-' * len(title)}\n{body}"
    return f"{title}\n{'-' * len(title)}"
