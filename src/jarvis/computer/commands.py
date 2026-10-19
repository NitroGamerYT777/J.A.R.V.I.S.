"""Unambiguous offline shortcuts; all other language goes through the AI router."""
import json
import re

from jarvis.intent import AIIntent
from .catalog import validate_action


def command(skill, args):
    return AIIntent('command', 'Lokal kompyuter topshirig‘i tayyorlandi.', 'computer', 'computer_action',
                    json.dumps({'skill': skill, 'args': args}, ensure_ascii=False))


def local_computer_intent(message):
    text = message.strip().replace('‘', "'").replace('’', "'").replace('ʻ', "'")
    match = re.fullmatch(r"(?:fayl(?:ni)?\s+(?:top|qidir|izla)\s*:\s*)(.+)", text, re.I)
    if not match:
        match = re.fullmatch(r"(.+?)\s+nomli\s+faylni\s+(?:top|qidir|izla)[.!]?", text, re.I)
    if match:
        return command('file_find', {'query': match[1].strip(' \"')})
    exact = {"mrt bilan virusni tekshir": 'mrt_open', 'mrtni och': 'mrt_open',
             'mrt hisobotini ko\'rsat': 'mrt_report', "defender holatini ko'rsat": 'security_status',
             'eng katta fayllarni top': 'largest_files', 'oxirgi fayllarni ko\'rsat': 'recent_files',
             'dublikat fayllarni top': 'duplicates', "disk holatini ko'rsat": 'disk_info'}
    skill = exact.get(text.casefold().strip(' .!?'))
    if skill:
        return command(skill, {})
    match = re.fullmatch(r"(.+?)\s+ilovasini\s+och[.!]?", text, re.I)
    if match:
        return command('app_open', {'name': match[1].strip()})
    return None


def ground_computer_intent(message, intent):
    if intent.command != 'computer_action':
        return intent
    try:
        skill, args = validate_action(json.loads(intent.target))
        normalize = lambda value: value.replace('\\', '/').casefold()
        text = normalize(message)
        for field in ('path', 'other', 'root', 'destination'):
            value = args.get(field, '')
            if value and normalize(value) not in text:
                return AIIntent('answer', 'Fayl yo‘lini taxmin qilmayman. Computer Hub’da fayl/papkani tanlang yoki kerakli yo‘lni yozing.')
        return intent
    except (ValueError, TypeError):
        return AIIntent('answer', 'Kompyuter topshirig‘i parametrlari noaniq. Computer Hub orqali aniq amal va faylni tanlang.')
