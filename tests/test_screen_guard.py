"""F04 + F06: the screen guard picks windows by process, and repeated warnings are per contact."""
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("screen guard is Windows only", allow_module_level=True)

from guard.screen_guard import alert_key, watched_app  # noqa: E402


def test_window_chosen_by_process_not_title():
    assert watched_app("Roblox", "RobloxPlayerBeta.exe") == "Roblox"
    assert watched_app("anything", "Discord.exe") == "Discord"
    # a browser tab or document merely titled like a game is not watched
    assert watched_app("Roblox - Google Chrome", "chrome.exe") is None
    assert watched_app("Discord tips.docx - Word", "winword.exe") is None
    assert watched_app("Minecraft 1.21", "javaw.exe") == "Minecraft"
    assert watched_app("Some Java tool", "javaw.exe") is None
    assert watched_app("BlockQuest chat (Night Guard live demo) - Google Chrome", "chrome.exe") == "Roblox"


def test_same_words_from_another_contact_warn_again():
    msgs = [{"from": "them", "name": "Alex_17", "text": "keep it secret"},
            {"from": "them", "name": "Sam", "text": "keep it secret"}]
    a = alert_key("WhatsApp", {"id": "secrecy", "message_index": 0, "quote": "keep it secret"}, msgs)
    b = alert_key("WhatsApp", {"id": "secrecy", "message_index": 1, "quote": "keep it secret"}, msgs)
    c = alert_key("WhatsApp", {"id": "secrecy", "message_index": 0, "quote": "Keep it secret "}, msgs)
    assert a != b and a == c


def test_kuririn_002_bank_window_is_not_discord():
    assert watched_app("Bank statement - Discord receipts - Chrome", "chrome.exe") is None
