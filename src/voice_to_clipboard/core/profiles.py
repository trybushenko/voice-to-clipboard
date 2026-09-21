"""Validated language profiles; no speech backend is imported during setup."""
import copy
import re

LANGUAGES = ('af', 'am', 'ar', 'as', 'az', 'ba', 'be', 'bg', 'bn', 'bo', 'br', 'bs', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'en', 'es', 'et', 'eu', 'fa', 'fi', 'fo', 'fr', 'gl', 'gu', 'ha', 'haw', 'he', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jw', 'ka', 'kk', 'km', 'kn', 'ko', 'la', 'lb', 'ln', 'lo', 'lt', 'lv', 'mg', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl', 'nn', 'no', 'oc', 'pa', 'pl', 'ps', 'pt', 'ro', 'ru', 'sa', 'sd', 'si', 'sk', 'sl', 'sn', 'so', 'sq', 'sr', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'uk', 'ur', 'uz', 'vi', 'yi', 'yo', 'zh', 'yue')
LANGUAGE_NAMES = {'en': 'English', 'uk': 'Ukrainian', 'pl': 'Polish', 'de': 'German',
                 'fr': 'French', 'es': 'Spanish', 'it': 'Italian', 'pt': 'Portuguese',
                 'ja': 'Japanese', 'zh': 'Chinese', 'ko': 'Korean', 'ar': 'Arabic',
                 'hi': 'Hindi', 'nl': 'Dutch', 'cs': 'Czech', 'sv': 'Swedish'}
NEW_PROFILES = [{'language': 'en', 'key': 'e', 'paste': False, 'model': ''}]
LEGACY_PROFILES = [{'language': 'uk', 'key': 'u', 'paste': False, 'model': ''},
                   *NEW_PROFILES, {'language': 'uk', 'key': 'l', 'paste': True, 'model': ''}]


def defaults(legacy=False):
    return copy.deepcopy(LEGACY_PROFILES if legacy else NEW_PROFILES)


def validate(profiles):
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 26:
        raise ValueError('Create between 1 and 26 language profiles')
    result, keys = [], set()
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError('Each profile must be an object')
        lang, key = profile.get('language'), profile.get('key')
        if lang not in LANGUAGES:
            raise ValueError('Choose a supported Whisper language code')
        if not isinstance(key, str) or not re.fullmatch('[a-zA-Z]', key):
            raise ValueError('Choose one shortcut letter A–Z')
        key = key.lower()
        if key in keys:
            raise ValueError('Shortcut letters must be unique across profiles')
        keys.add(key)
        paste, model = profile.get('paste', False), profile.get('model', '')
        if type(paste) is not bool or not isinstance(model, str) or len(model) > 300:
            raise ValueError('Choose clipboard/paste and a valid model name')
        model = model.strip()
        if lang != 'en' and model.endswith('.en'):
            raise ValueError('English-only .en models cannot transcribe other languages')
        result.append(dict(language=lang, key=key, paste=paste, model=model))
    return result


def label(profile):
    return LANGUAGE_NAMES.get(profile['language'], profile['language']) + ' (' + profile['key'].upper() + ')'
