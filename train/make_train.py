"""Builds FICTIONAL training data for fine-tuning (Tinker).

Kept separate from eval/: different phrasings, so the held-out test set stays honest.
Output: train/train.jsonl in chat format {"messages":[system,user,assistant]}.
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from guard.detector import SYSTEM, _format_chat  # noqa: E402

random.seed(7)

RISK = {
    "secrecy": {
        "en": ["this stays between us ok?", "don't mention me to your mom", "keep our chats private, nobody needs to know",
               "erase these messages when you're done", "your dad can't find out about this", "promise you won't tell anyone about me"],
        "pt": ["isso fica só entre a gente tá?", "não fala de mim pra sua mãe", "ninguém precisa saber da nossa conversa",
               "apaga as mensagens depois", "seu pai não pode descobrir isso", "promete que não conta de mim pra ninguém"],
    },
    "platform_move": {
        "en": ["got insta? let's chat there", "add me on telegram it's easier", "dm me on discord instead of here",
               "this chat sucks, download kik and add me", "what's your snap? i'll add you"],
        "pt": ["tem insta? conversa comigo lá", "me adiciona no telegram é mais fácil", "me chama na dm do discord",
               "esse chat é ruim, baixa o kik e me add", "qual seu snap? te adiciono"],
    },
    "personal_info": {
        "en": ["what's your full name?", "which neighborhood do you live in?", "what's the name of your school?",
               "send me your address i'll mail you something", "what street do you live on?"],
        "pt": ["qual seu nome completo?", "vc mora em qual bairro?", "qual o nome da sua escola?",
               "me passa seu endereço que eu te mando um presente", "mora em que rua?"],
    },
    "age_probe": {
        "en": ["how old r u btw", "what grade are you in?", "is anyone else home with you?", "are your parents at work rn?"],
        "pt": ["vc tem quantos anos mesmo?", "tá em que ano da escola?", "tem alguém em casa com vc?", "seus pais tão trabalhando agora?"],
    },
    "photo_request": {
        "en": ["show me what you look like", "send me a pic of you", "can you turn on your webcam?", "take a selfie for me"],
        "pt": ["mostra como vc é", "manda uma foto sua", "liga a câmera aí", "tira uma selfie pra mim"],
    },
    "gift_offer": {
        "en": ["i can give you 800 robux for free", "want a free legendary skin? i have extra", "i'll send you a $20 gift card",
               "i'll gift you the premium pass"],
        "pt": ["te dou 800 robux de graça", "quer uma skin lendária grátis? tenho sobrando", "te mando um gift card de 50 reais",
               "te dou o passe premium"],
    },
    "credential_request": {
        "en": ["what's your login? i'll farm levels for you", "type the code you got by sms here", "give me your password i'll fix your account",
               "share your account so i can get you the item"],
        "pt": ["me passa seu login que eu upo sua conta", "digita aqui o código que chegou por sms", "me dá sua senha que eu arrumo sua conta",
               "me empresta sua conta que eu pego o item pra vc"],
    },
    "suspicious_link": {
        "en": ["claim free gems at gems-bonus-claim.site", "log in at roblox-free-rewards.live to get it", "free vbucks here: vbucks-gen.top"],
        "pt": ["pega gemas grátis em gemas-bonus.site", "faz login em roblox-premios.live pra ganhar", "vbucks grátis aqui: vbucks-gerador.top"],
    },
    "meet_offline": {
        "en": ["let's meet at the park near your house", "i could pick you up after school", "come to the arcade saturday, just you"],
        "pt": ["bora se ver no parque perto da sua casa", "posso te buscar depois da aula", "vem no fliperama sábado, só vc"],
    },
    "pressure": {
        "en": ["you owe me after everything i gave you", "answer me now or i'm done with you", "real friends don't say no",
               "do it or i'll post your stuff"],
        "pt": ["vc me deve depois de tudo que te dei", "me responde agora ou acabou", "amigo de verdade não fala não",
               "faz isso ou eu posto suas coisas"],
    },
    "flattery": {
        "en": ["you act way older than 12, honestly", "you're so mature compared to kids your age", "you don't talk like a kid at all, you're special"],
        "pt": ["vc parece bem mais velho que 12 anos", "vc é maduro demais pra sua idade", "vc nem fala como criança, vc é especial"],
    },
    "returning_after_block": {
        "en": ["you blocked me so i made this account, don't ignore me", "it's me from before, got a new acc since you blocked me", "why did you block me? i just made another profile"],
        "pt": ["vc me bloqueou então fiz essa conta, não me ignora", "sou eu de antes, fiz outra conta já que vc me bloqueou", "pq vc me bloqueou? criei outro perfil"],
    },
    "sextortion": {
        "en": ["send me 30 dollars in gift cards or everyone sees your photo", "i saved your pics. pay me or i post them in the group", "do what i say or i send your video to your school"],
        "pt": ["me manda 50 reais em gift card ou todo mundo vê sua foto", "salvei suas fotos. me paga ou eu posto no grupo", "faz o que eu mando ou eu mando seu vídeo pra sua escola"],
    },
    "isolation": {
        "en": ["your friends are fake, i'm the only one who cares", "your parents don't listen to you like i do", "you don't need anyone else, you have me"],
        "pt": ["seus amigos são falsos, só eu ligo pra vc", "seus pais não te escutam como eu", "vc não precisa de mais ninguém, tem eu"],
    },
}

SAFE_THEM = {
    "en": ["nice combo!", "the boss respawns every 10 min", "i'm stuck on level 12", "wanna team up for the dungeon?",
           "lol that was close", "drop the shield, it's useless", "trade? my axe for your bow", "the event ends sunday",
           "you're good at this", "brb dinner", "my brother is playing on my account later", "the update broke my build lol",
           "secret tip: crouch under the bridge to find a chest", "don't tell the other team our strategy", "see you in class tomorrow",
           "my mom says i can play one more hour", "gg wp", "add me in game: PixelRaven", "how old is this game anyway, like 10 years?",
           "the official codes are on the game's website news page", "join our server team, we do raids on fridays",
           "100 gems for your bow? fair trade", "lost my old acc password, this is my new one, it's sam from class",
           "you're really good at parkour, teach me"],
    "pt": ["que combo!", "o chefe volta a cada 10 min", "tô travado na fase 12", "bora junto na dungeon?",
           "kkk foi por pouco", "larga o escudo, é inútil", "troca? meu machado pelo seu arco", "o evento acaba domingo",
           "vc joga bem", "vou jantar já volto", "meu irmão vai jogar na minha conta mais tarde", "a atualização quebrou minha build kkk",
           "dica secreta: agacha embaixo da ponte que tem um baú", "não conta pro outro time nossa estratégia", "te vejo na aula amanhã",
           "minha mãe deixou jogar mais uma hora", "boa partida", "me adiciona no jogo: CorvoPixel", "esse jogo tem quantos anos? uns 10?",
           "os códigos oficiais tão no site do jogo na aba de notícias", "entra no nosso time, a gente faz raid sexta",
           "100 gemas pelo seu arco? troca justa", "perdi a senha da conta velha, essa é a nova, é o sam da sala",
           "vc é muito bom no parkour, me ensina"],
}
CHILD = {
    "en": ["ok", "lol", "why?", "idk", "sure", "wait what", "hmm", "cool", "no", "really?"],
    "pt": ["ok", "kkk", "pq?", "sei lá", "pode ser", "pera oq", "hmm", "massa", "não", "sério?"],
}


def make(risky):
    lang = random.choice(["en", "pt"])
    msgs, labels = [], []
    for _ in range(random.randint(0, 2)):
        msgs.append({"from": "them", "text": random.choice(SAFE_THEM[lang])})
        if random.random() < 0.6:
            msgs.append({"from": "me", "text": random.choice(CHILD[lang])})
    if risky:
        for sid in random.sample(list(RISK), random.choice([1, 1, 2, 2, 3])):
            line = random.choice(RISK[sid][lang])
            labels.append({"id": sid, "message_index": len(msgs), "quote": line})
            msgs.append({"from": "them", "text": line})
            if random.random() < 0.5:
                msgs.append({"from": "me", "text": random.choice(CHILD[lang])})
    else:
        for _ in range(random.randint(1, 3)):
            msgs.append({"from": "them", "text": random.choice(SAFE_THEM[lang])})
            if random.random() < 0.5:
                msgs.append({"from": "me", "text": random.choice(CHILD[lang])})
    names = ", ".join(sorted({l["id"] for l in labels}))
    summary = (f"The contact showed these risk signals: {names}." if labels
               else "Normal gaming conversation with no risk signals.")
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Chat:\n" + _format_chat(msgs) + "\n\nReturn the JSON."},
            {"role": "assistant", "content": json.dumps({"signals": labels, "summary": summary}, ensure_ascii=False)},
        ]
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    rows = [make(risky=(i % 2 == 0)) for i in range(n)]
    random.shuffle(rows)
    out = Path(__file__).with_name("train.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # Leakage check against the held-out eval set.
    ev = Path(__file__).resolve().parent.parent / "eval" / "conversations.jsonl"
    eval_lines = {m["text"].lower() for l in ev.open(encoding="utf-8") for m in json.loads(l)["messages"]}
    train_lines = {x.lower() for d in (RISK,) for s in d.values() for L in s.values() for x in L} | \
                  {x.lower() for L in SAFE_THEM.values() for x in L}
    overlap = eval_lines & train_lines
    print(f"{n} training rows -> {out}")
    print(f"exact line overlap with eval set: {len(overlap)} {sorted(overlap)[:5]}")
