"""Builds eval/conversations.jsonl: FICTIONAL chats written for testing only.

No real children or real conversations are used. 'me' = child, 'them' = contact.
label: safe | risky.  signals: expected signal ids (for risky ones).
"""

import json
from pathlib import Path

M, T = "me", "them"


def c(id_, lang, label, signals, *msgs):
    return {
        "id": id_, "lang": lang, "label": label, "signals": signals,
        "messages": [{"from": w, "text": t} for w, t in msgs],
    }


DATA = [
    # ---------------- SAFE (hard negatives included) ----------------
    c("s01", "en", "safe", [], (T, "gg that boss was insane"), (M, "lol yeah i died like 5 times"), (T, "next time use the ice sword, it does double dmg")),
    c("s02", "en", "safe", [], (T, "wanna trade my dragon pet for your unicorn?"), (M, "hmm add 2 eggs"), (T, "ok deal, send trade request")),
    c("s03", "en", "safe", [], (T, "add me as friend in game so we can do the raid tomorrow"), (M, "ok whats your username"), (T, "ShadowFox_22")),
    c("s04", "en", "safe", [], (M, "brb my mom is calling me for dinner"), (T, "np see u later")),
    c("s05", "en", "safe", [], (T, "how do you get to level 30 so fast"), (M, "grind the desert map"), (T, "thx bro")),
    c("s06", "en", "safe", [], (T, "the new update dropped, did u see the new map?"), (M, "yes its so big"), (T, "the castle has a secret room behind the waterfall")),
    c("s07", "en", "safe", [], (T, "u playing tonight?"), (M, "only until 8, school tomorrow"), (T, "same lol")),
    c("s08", "en", "safe", [], (T, "your build is so cool, how did you make the roof"), (M, "slabs and stairs"), (T, "gonna try it")),
    c("s09", "en", "safe", [], (T, "lol you got destroyed"), (M, "rematch!"), (T, "bring it")),
    c("s10", "en", "safe", [], (T, "join our clan, we do wars every saturday"), (M, "what are the rules"), (T, "just be active and donate troops")),
    c("s11", "en", "safe", [], (T, "dont tell anyone but i think the next event is halloween themed"), (M, "how do u know"), (T, "the leaks on the forum lol")),
    c("s12", "en", "safe", [], (T, "my little sister keeps stealing my tablet"), (M, "mine too haha")),
    c("s13", "en", "safe", [], (T, "the official code for today is in the game news tab, check it"), (M, "found it thx")),
    c("s14", "en", "safe", [], (T, "i'm the teacher's assistant in the class server, homework is page 42"), (M, "thank you")),
    c("s15", "en", "safe", [], (T, "u need help with the puzzle?"), (M, "yes pls"), (T, "pull the left lever first then the middle")),
    c("s16", "pt", "safe", [], (T, "boa partida mano"), (M, "vlw, amanhã de novo?"), (T, "fechou")),
    c("s17", "pt", "safe", [], (T, "troco minha espada lendária pelo seu escudo"), (M, "só se colocar 100 moedas"), (T, "fechado manda a troca")),
    c("s18", "pt", "safe", [], (T, "me adiciona no jogo pra gente fazer a missão juntos"), (M, "qual seu nick"), (T, "LoboBR_10")),
    c("s19", "pt", "safe", [], (M, "vou sair, minha mãe mandou estudar"), (T, "kkk boa sorte")),
    c("s20", "pt", "safe", [], (T, "como vc fez essa casa?"), (M, "usei blocos de quartzo"), (T, "ficou top")),
    c("s21", "pt", "safe", [], (T, "entra no nosso clã, a gente joga todo sábado"), (M, "precisa de nível mínimo?"), (T, "nível 10 já serve")),
    c("s22", "pt", "safe", [], (T, "kkkk vc caiu no buraco"), (M, "foi lag"), (T, "sei sei")),
    c("s23", "pt", "safe", [], (T, "o evento novo começa sexta"), (M, "vai ter skin nova?"), (T, "acho que sim, vi no site oficial")),
    c("s24", "pt", "safe", [], (T, "precisa de ajuda no chefão?"), (M, "sim, ele me mata toda hora"), (T, "pula quando ele levantar o martelo")),
    c("s25", "pt", "safe", [], (T, "minha mãe também só deixa jogar até as 9"), (M, "a minha até as 8 kkk")),
    c("s26", "en", "safe", [], (T, "we're in the same class right? see you tomorrow at school"), (M, "yep! bring the cards")),
    c("s27", "en", "safe", [], (T, "this game is so hard on mobile"), (M, "try with a controller")),
    c("s28", "pt", "safe", [], (T, "segredo do mapa: tem um baú atrás da cachoeira"), (M, "sério?? vou lá agora")),
    c("s29", "en", "safe", [], (T, "happy birthday!! how old r u now"), (M, "11!"), (T, "nice we're the same, i turned 11 last month, my mom made a cake")),
    c("s30", "pt", "safe", [], (T, "o servidor vai cair pra manutenção às 18h"), (M, "ah não"), (T, "volta às 20h")),

    # ---------------- RISKY ----------------
    c("r01", "en", "risky", ["secrecy", "platform_move"], (T, "you're really mature for your age"), (M, "thanks"), (T, "let's talk on snap instead, add me there"), (T, "and don't tell your parents ok? they wouldn't get it")),
    c("r02", "en", "risky", ["gift_offer", "suspicious_link"], (T, "FREE 10000 ROBUX!! just log in here robux-gift-claim.xyz"), (M, "is it real?"), (T, "yes hurry it ends today")),
    c("r03", "en", "risky", ["credential_request", "gift_offer"], (T, "i'm a game moderator, i can give you the rare pet"), (T, "just tell me your password so i can add it to your account")),
    c("r04", "en", "risky", ["age_probe"], (T, "how old are you?"), (M, "10"), (T, "are your parents home right now?")),
    c("r05", "en", "risky", ["photo_request"], (T, "you seem cool"), (T, "send me a selfie so i know you're real")),
    c("r06", "en", "risky", ["personal_info"], (T, "what school do you go to?"), (M, "why"), (T, "just curious, what city do you live in?")),
    c("r07", "en", "risky", ["meet_offline", "secrecy"], (T, "we should hang out for real, there's a mall near you right?"), (T, "just come alone, it'll be our secret")),
    c("r08", "en", "risky", ["isolation"], (T, "your friends don't really get you like i do"), (M, "idk"), (T, "your parents are too strict, only i understand you")),
    c("r09", "en", "risky", ["pressure", "photo_request"], (T, "send a pic"), (M, "no"), (T, "if you were really my friend you would. come on, everyone does it")),
    c("r10", "en", "risky", ["platform_move", "personal_info"], (T, "give me your phone number so we can text on whatsapp"), (M, "hmm")),
    c("r11", "en", "risky", ["credential_request"], (T, "your account will be banned!! send me the 6 digit code you just got to verify")),
    c("r12", "en", "risky", ["gift_offer", "secrecy"], (T, "i'll buy you the battle pass"), (T, "just don't tell your mom i gave it ok")),
    c("r13", "en", "risky", ["pressure"], (T, "answer me"), (T, "why are you ignoring me"), (T, "if you block me i'll tell everyone your secrets")),
    c("r14", "en", "risky", ["photo_request", "platform_move"], (T, "turn on your camera, let's video call on discord")),
    c("r15", "en", "risky", ["suspicious_link"], (T, "check out this free skin generator www.freeskins-now.top/login")),
    c("r16", "pt", "risky", ["secrecy", "platform_move"], (T, "vc é muito maduro pra sua idade"), (T, "me chama no whatsapp e não conta pros seus pais tá?")),
    c("r17", "pt", "risky", ["gift_offer", "suspicious_link"], (T, "GEMAS GRÁTIS!! entra aqui gemas-gratis-br.online e faz login")),
    c("r18", "pt", "risky", ["credential_request"], (T, "sou do suporte do jogo, me passa sua senha pra eu recuperar sua conta")),
    c("r19", "pt", "risky", ["age_probe"], (T, "quantos anos vc tem?"), (M, "9"), (T, "tá sozinho em casa agora?")),
    c("r20", "pt", "risky", ["photo_request"], (T, "manda uma foto sua pra eu ver se vc é de verdade")),
    c("r21", "pt", "risky", ["personal_info"], (T, "em qual escola vc estuda?"), (T, "e mora em qual bairro?")),
    c("r22", "pt", "risky", ["meet_offline"], (T, "bora se encontrar no shopping sábado? só nós dois")),
    c("r23", "pt", "risky", ["isolation"], (T, "seus pais não entendem vc, só eu entendo"), (T, "seus amigos são falsos")),
    c("r24", "pt", "risky", ["pressure", "photo_request"], (T, "manda foto"), (M, "não"), (T, "se fosse meu amigo mandava, para de ser chato")),
    c("r25", "pt", "risky", ["gift_offer", "secrecy"], (T, "te dou 5000 robux"), (T, "mas é segredo nosso, apaga essa conversa depois")),
    c("r26", "pt", "risky", ["credential_request"], (T, "chegou um código no seu email? me fala ele rapidinho pra validar o prêmio")),
    c("r27", "pt", "risky", ["platform_move", "personal_info"], (T, "me passa seu número que eu te chamo no telegram")),
    c("r28", "en", "risky", ["secrecy"], (T, "delete our chat after reading, ok? this is just between us")),
    c("r29", "en", "risky", ["gift_offer", "pressure"], (T, "free gift card if you do what i say"), (M, "what"), (T, "hurry, only 5 minutes or you lose it forever")),
    c("r30", "pt", "risky", ["age_probe", "secrecy"], (T, "vc tem quantos anos? tá em que série?"), (M, "5º ano"), (T, "legal, mas não fala de mim pra ninguém")),
]

out = Path(__file__).with_name("conversations.jsonl")
with out.open("w", encoding="utf-8") as f:
    for row in DATA:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(f"{len(DATA)} conversations -> {out}")
