"""Night Guard film, Portuguese version: narration (Antonio, edge-tts) and timeline.

Run:  python video/script_pt.py   -> video/voz_pt/n*.mp3 and video/timeline_pt.json
"""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

HERE = Path(__file__).parent
VOICE = "pt-BR-AntonioNeural"

# scene id, narration, extra seconds after the line
SCENES = [
    ("night", "São onze da noite. Uma criança joga online. E alguém está sendo gentil demais com ela.", 1.4),
    ("stat", "Só em 2025, a central americana de crianças desaparecidas e exploradas recebeu mais de cinquenta mil "
             "denúncias de sextorsão. São cento e trinta e sete por dia. Quase uma a cada dez minutos.", 1.2),
    ("fast", "E pode ser rápido. Num estudo da Universidade de Swansea, o primeiro pedido sexual veio em apenas dezoito minutos.", 1.0),
    ("platforms", "Roblox, Discord, Minecraft, TikTok. Cada plataforma vigia só o próprio quintal. E o golpista sabe disso: "
                  "ele puxa a criança para um aplicativo criptografado, onde ninguém mais vê.", 1.2),
    ("parents", "Os pais não conseguem ler cada conversa. E a criança nem sempre percebe a armadilha.", 1.4),
    ("guard", "Conheça o Night Guard. Um modelo aberto que roda no computador da própria família. Ele lê o que aparece na tela, "
              "então protege até dentro do aplicativo criptografado. E a conversa nunca sai de casa.", 0.8),
    ("alert", "Quando um estranho pede segredo, ele avisa na hora, com palavras que a criança entende.", 10.6),
    ("hero", "Para a criança, ele é um amigo. Cada truque que ela aprende vira medalha, até ela virar a heroína da noite.", 1.2),
    ("family", "Para os pais, ele é o Guarda Noturno. Um alerta só, sem a conversa inteira. O que aconteceu, e o que fazer agora, "
               "direto no celular.", 1.4),
    ("tech", "Por dentro, só tecnologia aberta. O Gemma 4 lê texto e tela no próprio computador. No Tinker, treinamos um modelo "
             "que acertou o formato em setenta de setenta conversas. O Temporal aguenta queda, o Sentry acompanha cada "
             "checagem sem ler a conversa, o ElevenLabs dá voz aos avisos, e a demonstração roda no Render.", 1.0),
    ("results", "Nos testes, pegou trinta e seis de trinta e seis conversas de risco, em uns quatro segundos.", 1.4),
    ("peace", "Paz para a criança. Paz para os pais. E quanto mais a criança aprende, mais o guarda pode descansar.", 1.6),
    ("end", "Night Guard. Parceiro dos pais. Amigo das crianças.", 3.0),
]


async def speak(text, out):
    await edge_tts.Communicate(text, VOICE, rate="-4%").save(str(out))


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


async def main():
    (HERE / "voz_pt").mkdir(exist_ok=True)
    t, timeline = 1.2, []
    for i, (sid, line, extra) in enumerate(SCENES, 1):
        out = HERE / "voz_pt" / f"n{i}.mp3"
        await speak(line, out)
        d = duration(out)
        timeline.append({"id": sid, "line": line, "voice": out.name, "start": round(t, 2),
                         "voice_dur": round(d, 2), "end": round(t + d + extra, 2)})
        t += d + extra
    (HERE / "timeline_pt.json").write_text(json.dumps({"scenes": timeline, "duration": round(t + 0.3, 2)},
                                                      indent=2, ensure_ascii=False), encoding="utf-8")
    for s in timeline:
        print(f"{s['id']:9} {s['start']:6.2f} -> {s['end']:6.2f}  ({s['voice_dur']}s voice)")
    print("total", round(t + 0.3, 2), "s")


if __name__ == "__main__":
    asyncio.run(main())
