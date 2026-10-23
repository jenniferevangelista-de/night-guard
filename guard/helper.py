"""'Tell someone': a short, editable help message the child can send to a trusted adult.

The message is built only from what the child chose: the flagged quotes and their own words.
Earlier versions let a model write it, but it sometimes addressed the wrong person or invented
what the child did, which is unacceptable here. Nothing is sent automatically.
"""


def template_help(quotes, who="Mom", note="", lang="en"):
    """A calm message made only from the child's chosen quotes and own words (nothing invented)."""
    sep = " e " if lang == "pt" else " and "
    q = sep.join(f'"{x.strip()}"' for x in quotes if x.strip())
    note = note.strip().rstrip(".!?")
    note = (note[:1].upper() + note[1:] + ".") if note else ""
    if lang == "pt":
        first = f"{who}, alguém num jogo me mandou isto: {q}." if q else f"{who}, aconteceu uma coisa num jogo."
        last = "Eu não fiz nada de errado, mas preciso de ajuda. A gente pode conversar?"
    else:
        first = f"{who}, someone in a game sent me this: {q}." if q else f"{who}, something happened in a game."
        last = "I didn't do anything wrong, but I need help. Can we talk?"
    return " ".join(p for p in (first, note, last) if p)


def draft_help(quotes, who="Mom", note="", lang="en"):
    return template_help(quotes, who, note, "pt" if lang == "pt" else "en")
