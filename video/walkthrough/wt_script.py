"""Video 2 (walkthrough): Snoozy/Soneca narrates a real screen recording of every Night Guard feature.

  python video/walkthrough/wt_script.py pt     -> voz_pt/w*.mp3 + narr_pt.json
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts

HERE = Path(__file__).resolve().parent
VOICES = {"pt": ("pt-BR-AntonioNeural", "+10%"), "en": ("en-US-BrianMultilingualNeural", "+10%")}

LINES = {
    "pt": [
        ("home", "Oi, aqui é o Soneca de novo. Agora é o Night Guard de verdade, rodando no computador. No topo, a barra mostra "
                 "se o guarda está ligado. Um clique liga, outro desliga."),
        ("check", "Na aba Algo me incomodou, a criança cola uma conversa ou escolhe um exemplo. O Gemma analisa ali mesmo, "
                  "sem mandar nada pra internet."),
        ("result", "Primeiro ele pergunta o que ela acha. Depois mostra o perigo em palavras simples, com a frase exata do "
                   "estranho, e o que fazer. E dá pra ouvir o aviso."),
        ("benign", "E uma conversa normal de jogo? Nada de alarme falso."),
        ("practice", "Em Praticar, ela treina situações curtas. Cada acerto vira medalha, ela sobe de nível, e a barra mostra o "
                     "guarda ficando mais preguiçoso."),
        ("tell", "Em Contar pra alguém, ela escolhe o que compartilhar e recebe uma mensagem pronta pra mãe, pai ou professor. "
                 "Nada é enviado sozinho: quem decide é ela."),
        ("parents", "Na área dos pais, o Guarda Noturno mostra só o que importa: o risco, o app, o trecho e o que fazer agora. "
                    "Os pais escolhem as regras e podem receber aviso no celular."),
        ("game", "No modo ao vivo, ninguém cola nada. O estranho escreve no chat do jogo, e o guarda avisa a criança sozinho, "
                 "na hora, com voz."),
        ("off", "Desligou o guarda? Ele para na hora, até o que estava na fila."),
        ("fault", "E se o modelo cair, o selo vira Guarda pausado. Ele nunca finge que está tudo bem. Aqui a queda foi simulada."),
        ("end", "Tudo isso com modelo aberto, no computador da família. Night Guard: parceiro dos pais, amigo das crianças."),
    ],
    "en": [
        ("home", "Hi, Snoozy again. This is the real Night Guard, running on the computer. At the top, the bar shows whether "
                 "the guard is on. One click turns it on, another turns it off."),
        ("check", "In Something felt off, the kid pastes a chat or picks an example. Gemma checks it right there, without "
                  "sending anything to the internet."),
        ("result", "First it asks what she thinks. Then it shows the danger in plain words, with the stranger's exact message, "
                   "and what to do. And she can listen to the warning."),
        ("benign", "And a normal game chat? No false alarm."),
        ("practice", "In Practice, she tries short scenarios. Every right answer becomes a medal, she levels up, and the bar "
                     "shows the guard getting lazier."),
        ("tell", "In Tell someone, she picks what to share and gets a ready message for Mom, Dad or a teacher. Nothing is "
                 "sent on its own: she decides."),
        ("parents", "In the parents' area, the Night Guard shows only what matters: the risk, the app, the message and what "
                    "to do now. Parents set the rules and can get a phone alert."),
        ("game", "In live mode, nobody pastes anything. The stranger writes in the game chat, and the guard warns the kid "
                 "by itself, right away, out loud."),
        ("off", "Turned the guard off? It stops right away, even what was queued."),
        ("fault", "And if the model goes down, the badge says Guard paused. It never pretends everything is fine. Here the "
                  "failure is simulated."),
        ("end", "All of this with an open model, on the family's own computer. Night Guard: a partner for parents, a friend "
                "for kids."),
    ],
}


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


async def main(lang):
    voice, rate = VOICES[lang]
    out_dir = HERE / f"voz_{lang}"; out_dir.mkdir(exist_ok=True)
    narr = []
    for i, (sid, line) in enumerate(LINES[lang], 1):
        f = out_dir / f"w{i:02d}.mp3"
        await edge_tts.Communicate(line, voice, rate=rate).save(str(f))
        narr.append({"id": sid, "line": line, "voice": f"voz_{lang}/{f.name}", "dur": round(duration(f), 2)})
    (HERE / f"narr_{lang}.json").write_text(json.dumps(narr, indent=2, ensure_ascii=False), encoding="utf-8")
    for n in narr:
        print(f"{n['id']:9} {n['dur']:5.2f}s")
    print("total voice", round(sum(n["dur"] for n in narr), 1))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "pt"))
