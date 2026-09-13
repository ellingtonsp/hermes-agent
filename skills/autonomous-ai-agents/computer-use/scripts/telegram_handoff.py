#!/usr/bin/env python3
"""Send an optional Telegram takeover button; return control via normal chat.

No polling, callback listener, credential forwarding or implicit task resume.
Requires python-dotenv (bundled with Hermes). Use --dry-run before sending.
"""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request


def build_card(chat_id, url, reason, task):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('Use a configured HTTPS launcher without credentials, query or fragment')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', task):
        raise ValueError('Task ID must be 1-48 letters, digits, underscores or hyphens')
    if not reason.strip() or len(reason) > 1000:
        raise ValueError('A short, non-secret reason and on-screen instruction are required')
    if not re.fullmatch(r'-?[0-9]+', str(chat_id)):
        raise ValueError('Use an explicit numeric originating chat ID')
    return {
        'chat_id': str(chat_id),
        'text': (f'Your help needed — {task}\n{reason.strip()}\n\n'
                 f'Desktop input is paused. Return here and reply “resume {task}” '
                 'when finished, or “cancel”. I will verify the screen before continuing.'),
        'link_preview_options': {'is_disabled': True},
        'reply_markup': {'inline_keyboard': [[{'text': 'Take over desktop', 'url': url}]]},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chat-id', required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--thread-id', type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    card = build_card(args.chat_id, args.url, args.reason, args.task)
    if args.thread_id is not None:
        card['message_thread_id'] = args.thread_id
    if args.dry_run:
        print(json.dumps(card, ensure_ascii=False))
        return
    from dotenv import dotenv_values
    home = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    token = os.environ.get('TELEGRAM_BOT_TOKEN') or dotenv_values(home / '.env').get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise SystemExit('Telegram is not configured for this profile')
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps(card).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.load(response)
    except (urllib.error.URLError, TimeoutError):
        # Exceptions can include the credential-bearing request URL. Never log them.
        raise SystemExit('Telegram request failed or timed out. Delivery may be uncertain; do not blindly resend.') from None
    if not result.get('ok'):
        raise SystemExit('Telegram rejected the handoff request')
    message = result['result']
    print(json.dumps({'accepted': True, 'chat_id': message['chat']['id'],
                      'message_id': message['message_id'], 'task': args.task}))


if __name__ == '__main__':
    main()
