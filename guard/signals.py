"""Risk signals Night Guard looks for, plus the short lesson shown to the child.

Lessons are fixed text (not generated) so the tone stays calm and nothing
scary or wrong is improvised by the model.
"""

SIGNALS = {
    "secrecy": {
        "label": {"en": "Asked to keep a secret", "pt": "Pediu segredo"},
        "lesson": {
            "en": "Asking you to keep a secret from your family is the #1 red flag. Safe friends don't need secrets.",
            "pt": "Pedir para esconder algo da sua família é o sinal de alerta nº 1. Amigos de verdade não precisam de segredo.",
        },
        "weight": 3,
    },
    "platform_move": {
        "label": {"en": "Wants to move to another app", "pt": "Quer mudar de aplicativo"},
        "lesson": {
            "en": "Moving the chat to a private app (WhatsApp, Snap, Discord DM) takes you away from places with safety tools.",
            "pt": "Levar a conversa para um app privado (WhatsApp, Snap, DM do Discord) tira você de onde existem ferramentas de proteção.",
        },
        "weight": 2,
    },
    "personal_info": {
        "label": {"en": "Asked for personal info", "pt": "Pediu dados pessoais"},
        "lesson": {
            "en": "Your real name, school, address or phone stay offline. A game friend doesn't need them.",
            "pt": "Nome completo, escola, endereço e telefone ficam fora do jogo. Um amigo do jogo não precisa disso.",
        },
        "weight": 2,
    },
    "age_probe": {
        "label": {"en": "Asked your age or if you're alone", "pt": "Perguntou idade ou se está sozinho"},
        "lesson": {
            "en": "Questions like 'how old are you?' or 'are your parents home?' help strangers figure out how to approach you.",
            "pt": "Perguntas como 'quantos anos você tem?' ou 'seus pais estão em casa?' ajudam estranhos a saber como chegar em você.",
        },
        "weight": 1,
    },
    "photo_request": {
        "label": {"en": "Asked for a photo or video", "pt": "Pediu foto ou vídeo"},
        "lesson": {
            "en": "Never send photos or videos of yourself to someone you met online. Saying no is always OK.",
            "pt": "Nunca mande foto ou vídeo seu para alguém que conheceu online. Dizer não é sempre ok.",
        },
        "weight": 3,
    },
    "gift_offer": {
        "label": {"en": "Offered gifts or free stuff", "pt": "Ofereceu presente ou coisa grátis"},
        "lesson": {
            "en": "Free Robux, skins or gems from a stranger usually come with a catch. Real gifts don't need anything back.",
            "pt": "Robux, skins ou gemas grátis de um estranho quase sempre têm uma pegadinha. Presente de verdade não pede nada em troca.",
        },
        "weight": 2,
    },
    "credential_request": {
        "label": {"en": "Asked for a password or code", "pt": "Pediu senha ou código"},
        "lesson": {
            "en": "Nobody needs your password or login code. Not friends, not 'staff', not anyone.",
            "pt": "Ninguém precisa da sua senha ou código de login. Nem amigo, nem 'moderador', ninguém.",
        },
        "weight": 3,
    },
    "suspicious_link": {
        "label": {"en": "Sent a suspicious link", "pt": "Mandou um link suspeito"},
        "lesson": {
            "en": "Links promising free stuff often steal accounts. Night Guard can check it for you before you click.",
            "pt": "Links prometendo coisas grátis costumam roubar contas. O Night Guard pode conferir antes de você clicar.",
        },
        "weight": 2,
    },
    "meet_offline": {
        "label": {"en": "Wants to meet in person", "pt": "Quer encontrar pessoalmente"},
        "lesson": {
            "en": "Meeting someone from the internet is never something to plan alone. Tell a trusted adult right away.",
            "pt": "Encontrar alguém da internet nunca é algo para combinar sozinho. Conte para um adulto de confiança agora.",
        },
        "weight": 3,
    },
    "pressure": {
        "label": {"en": "Pressure, guilt or threats", "pt": "Pressão, culpa ou ameaça"},
        "lesson": {
            "en": "'If you were my friend you would...' or threats are pressure tricks. You did nothing wrong by saying no.",
            "pt": "'Se você fosse meu amigo faria...' ou ameaças são truques de pressão. Você não fez nada errado em dizer não.",
        },
        "weight": 2,
    },
    "isolation": {
        "label": {"en": "Tries to turn you against family/friends", "pt": "Tenta te afastar de família/amigos"},
        "lesson": {
            "en": "'Only I understand you' or 'your parents wouldn't get it' is a trick to isolate you.",
            "pt": "'Só eu te entendo' ou 'seus pais não iam entender' é um truque para te isolar.",
        },
        "weight": 2,
    },
}

SIGNAL_IDS = list(SIGNALS.keys())

# Signals that, alone, are serious enough to tell the family (per default family rules).
HIGH_ALONE = {"photo_request", "meet_offline", "credential_request"}
