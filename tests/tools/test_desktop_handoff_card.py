"""Contract tests for the optional skill-side Telegram handoff card."""
import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).parents[2] / 'skills/autonomous-ai-agents/computer-use/scripts/telegram_handoff.py'

def load():
    spec = importlib.util.spec_from_file_location('handoff_card', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_card_keeps_transport_url_out_of_chat_text():
    card = load().build_card('123', 'https://mac.example:9123/', 'Complete SSO', 'demo-1')
    assert 'https://' not in card['text']
    assert card['reply_markup']['inline_keyboard'][0][0] == {
        'text': 'Take over desktop', 'url': 'https://mac.example:9123/'}
    assert 'resume demo-1' in card['text']
    assert card['link_preview_options']['is_disabled'] is True

@pytest.mark.parametrize('url', ['vnc://mac', 'http://mac/', 'https://user:secret@mac/', 'https://mac/?token=secret'])
def test_rejects_non_https_and_secret_bearing_links(url):
    with pytest.raises(ValueError):
        load().build_card('123', url, 'Complete SSO', 'demo-1')
