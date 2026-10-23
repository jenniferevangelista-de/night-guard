"""'Tell someone': drafts a short, editable help message the child can send.

Runs locally with Gemma. The child picks which parts to share; nothing is sent
automatically.
"""

import httpx

from .detector import BACKEND, MODEL, OLLAMA_URL

PROMPT = {
    "en": """Write a short message (max 4 sentences) that a child can send to a trusted adult ({who}).
Tone: calm, simple words a 10-year-old would use. Say what happened using the quotes below.
Make clear the child did nothing wrong and is asking for help, not in trouble.
Describe what the person ASKED for, quoting it; do not assume anything already happened.
Call them "someone from the game". Never use placeholders like [Name] or brackets.
Never invent how the child replied or what the child did (no "I said no", "I blocked them", "I hung up").
Do not add details that are not in the quotes. Do not use the word 'predator'. Output only the message.

What the contact wrote:
{quotes}
{note}""",
    "pt": """Escreva uma mensagem curta (máx. 4 frases) que uma criança possa mandar para um adulto de confiança ({who}).
Tom: calmo, palavras simples que uma criança de 10 anos usaria. Conte o que aconteceu usando os trechos abaixo.
Deixe claro que a criança não fez nada de errado e está pedindo ajuda, não está encrencada.
Conte o que a pessoa PEDIU, citando o trecho; não suponha que algo já aconteceu.
Chame a pessoa de "alguém do jogo". Nunca use espaços para preencher como [Nome] ou colchetes.
Nunca invente o que a criança respondeu ou fez (nada de "eu disse não", "eu bloqueei", "eu desliguei").
Não invente detalhes que não estão nos trechos. Não use a palavra 'predador'. Responda só com a mensagem.

O que o contato escreveu:
{quotes}
{note}""",
}


def template_help(quotes, who="Mom", note="", lang="en"):
    """A calm message made only from the child's chosen quotes and own words (nothing invented)."""
    sep = " e " if lang == "pt" else " and "
    q = sep.join(f'"{x}"' for x in quotes)
    note = note.strip()
    note = note[:1].upper() + note[1:] if note else ""
    if lang == "pt":
        parts = [f"{who}, alguém do jogo me mandou isto: {q}." if q else f"{who}, aconteceu uma coisa no jogo."]
        if note:
            parts.append(note.strip().rstrip(".") + ".")
        parts.append("Eu não fiz nada de errado, mas preciso de ajuda. A gente pode conversar?")
    else:
        parts = [f"{who}, someone from the game sent me this: {q}." if q else f"{who}, something happened in a game."]
        if note:
            parts.append(note.strip().rstrip(".") + ".")
        parts.append("I didn't do anything wrong, but I need help. Can we talk?")
    return " ".join(parts)


def draft_help(quotes, who="Mom", note="", lang="en"):
    lang = lang if lang in PROMPT else "en"
    q = "\n".join(f'- "{x}"' for x in quotes) or "- (no quotes chosen)"
    extra = (("Child's own words: " if lang == "en" else "Palavras da criança: ") + note) if note else ""
    content = PROMPT[lang].format(who=who, quotes=q, note=extra)
    if BACKEND == "tinker":
        # Public demo: the fine-tuned model is a classifier, and the base model tended to invent
        # what the child did, so the message is built only from the quotes the child picked.
        return template_help(quotes, who, note, lang)
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        # Same num_ctx as the detector so Ollama doesn't reload the model.
        "options": {"temperature": 0.2, "num_ctx": 4096},
        "messages": [{"role": "user", "content": content}],
    }
    r = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()
