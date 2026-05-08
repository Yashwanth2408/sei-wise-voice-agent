from pathlib import Path



def load_wise_faq_markdown(path: str) -> str:
    faq_path = Path(path)
    if not faq_path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {faq_path}")
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return faq_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    # Last resort keeps process alive if file has mixed bytes.
    return faq_path.read_text(encoding="utf-8", errors="ignore")

