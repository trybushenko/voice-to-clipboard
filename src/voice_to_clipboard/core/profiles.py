"""Validated language profiles; no speech backend is imported during setup."""
import copy
import re

LANGUAGES = ('af', 'am', 'ar', 'as', 'az', 'ba', 'be', 'bg', 'bn', 'bo', 'br', 'bs', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'en', 'es', 'et', 'eu', 'fa', 'fi', 'fo', 'fr', 'gl', 'gu', 'ha', 'haw', 'he', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jw', 'ka', 'kk', 'km', 'kn', 'ko', 'la', 'lb', 'ln', 'lo', 'lt', 'lv', 'mg', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl', 'nn', 'no', 'oc', 'pa', 'pl', 'ps', 'pt', 'ro', 'ru', 'sa', 'sd', 'si', 'sk', 'sl', 'sn', 'so', 'sq', 'sr', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'uk', 'ur', 'uz', 'vi', 'yi', 'yo', 'zh', 'yue')
LANGUAGE_NAMES = {'af': 'Afrikaans', 'am': 'Amharic', 'ar': 'Arabic', 'as': 'Assamese', 'az': 'Azerbaijani', 'ba': 'Bashkir', 'be': 'Belarusian', 'bg': 'Bulgarian', 'bn': 'Bengali', 'bo': 'Tibetan', 'br': 'Breton', 'bs': 'Bosnian', 'ca': 'Catalan', 'cs': 'Czech', 'cy': 'Welsh', 'da': 'Danish', 'de': 'German', 'el': 'Greek', 'en': 'English', 'es': 'Spanish', 'et': 'Estonian', 'eu': 'Basque', 'fa': 'Persian', 'fi': 'Finnish', 'fo': 'Faroese', 'fr': 'French', 'gl': 'Galician', 'gu': 'Gujarati', 'ha': 'Hausa', 'haw': 'Hawaiian', 'he': 'Hebrew', 'hi': 'Hindi', 'hr': 'Croatian', 'ht': 'Haitian Creole', 'hu': 'Hungarian', 'hy': 'Armenian', 'id': 'Indonesian', 'is': 'Icelandic', 'it': 'Italian', 'ja': 'Japanese', 'jw': 'Javanese', 'ka': 'Georgian', 'kk': 'Kazakh', 'km': 'Khmer', 'kn': 'Kannada', 'ko': 'Korean', 'la': 'Latin', 'lb': 'Luxembourgish', 'ln': 'Lingala', 'lo': 'Lao', 'lt': 'Lithuanian', 'lv': 'Latvian', 'mg': 'Malagasy', 'mi': 'Maori', 'mk': 'Macedonian', 'ml': 'Malayalam', 'mn': 'Mongolian', 'mr': 'Marathi', 'ms': 'Malay', 'mt': 'Maltese', 'my': 'Burmese', 'ne': 'Nepali', 'nl': 'Dutch', 'nn': 'Norwegian Nynorsk', 'no': 'Norwegian', 'oc': 'Occitan', 'pa': 'Punjabi', 'pl': 'Polish', 'ps': 'Pashto', 'pt': 'Portuguese', 'ro': 'Romanian', 'ru': 'Russian', 'sa': 'Sanskrit', 'sd': 'Sindhi', 'si': 'Sinhala', 'sk': 'Slovak', 'sl': 'Slovenian', 'sn': 'Shona', 'so': 'Somali', 'sq': 'Albanian', 'sr': 'Serbian', 'su': 'Sundanese', 'sv': 'Swedish', 'sw': 'Swahili', 'ta': 'Tamil', 'te': 'Telugu', 'tg': 'Tajik', 'th': 'Thai', 'tk': 'Turkmen', 'tl': 'Tagalog', 'tr': 'Turkish', 'tt': 'Tatar', 'uk': 'Ukrainian', 'ur': 'Urdu', 'uz': 'Uzbek', 'vi': 'Vietnamese', 'yi': 'Yiddish', 'yo': 'Yoruba', 'zh': 'Chinese', 'yue': 'Cantonese'}
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
        modifiers = profile.get('modifiers', '')
        if not isinstance(modifiers, str):
            raise ValueError('Profile modifiers must be text')
        if modifiers.strip():
            from ..platform.windows_hotkeys import parse_modifiers, MODIFIERS
            mask = parse_modifiers(modifiers.strip())
            result[-1]['modifiers'] = '+'.join(name for name, bit in MODIFIERS.items() if mask & bit)
    return result


def label(profile):
    shortcut = (profile.get('modifiers', '') + '+' if profile.get('modifiers') else '') + profile['key'].upper()
    return LANGUAGE_NAMES.get(profile['language'], profile['language']) + ' (' + shortcut + ')'


def language_options():
    return [f"{LANGUAGE_NAMES[code]} ({code})" for code in sorted(LANGUAGES, key=LANGUAGE_NAMES.get)]


def language_code(text):
    text = text.strip()
    if text in LANGUAGES:
        return text
    for code, name in LANGUAGE_NAMES.items():
        if text.casefold() in (name.casefold(), f"{name} ({code})".casefold()):
            return code
    raise ValueError('Choose a language from the list')


def saved_profiles(response):
    if not isinstance(response, dict) or 'profiles' not in response:
        raise RuntimeError('The running host does not support language profiles. Quit Voice to Clipboard from the tray, then relaunch the updated app.')
    return validate(response['profiles'])
