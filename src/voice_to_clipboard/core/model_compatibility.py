"""Offline language metadata, not a backend/download availability guarantee.

Sources and deliberate limits are documented in docs/setup/model-compatibility.md.
Unknown repositories and paths are never inferred from their basename.
"""
MULTILINGUAL = ('tiny', 'base', 'small', 'medium', 'large-v1', 'large-v2',
                'large-v3', 'large', 'large-v3-turbo', 'turbo')
ENGLISH = ('tiny.en', 'base.en', 'small.en', 'medium.en', 'distil-small.en',
           'distil-medium.en', 'distil-large-v2', 'distil-large-v3', 'distil-large-v3.5')
# Offer portable standard names; custom/backend-specific names remain editable.
CHOICES = ('', 'large-v3-turbo', 'tiny', 'base', 'small', 'medium', 'large-v3',
           'tiny.en', 'base.en', 'small.en', 'medium.en')
ALIASES = {name: name for name in MULTILINGUAL + ENGLISH}
for name in ('tiny', 'base', 'small', 'medium', 'large-v1', 'large-v2', 'large-v3',
             'tiny.en', 'base.en', 'small.en', 'medium.en'):
    ALIASES['Systran/faster-whisper-' + name] = name
    ALIASES['openai/whisper-' + name] = name
    ALIASES['mlx-community/whisper-' + name + '-mlx'] = name
for name in ('distil-small.en', 'distil-medium.en', 'distil-large-v2', 'distil-large-v3'):
    ALIASES['Systran/faster-distil-whisper-' + name.removeprefix('distil-')] = name
    ALIASES['distil-whisper/' + name] = name
ALIASES.update({'mlx-community/whisper-large-v3-turbo': 'large-v3-turbo',
                'openai/whisper-large-v3-turbo': 'large-v3-turbo',
                'mobiuslabsgmbh/faster-whisper-large-v3-turbo': 'large-v3-turbo',
                'distil-whisper/distil-large-v3.5-ct2': 'distil-large-v3.5'})


def describe(language, model='', default=''):
    """Return (compatible/incompatible/unverified, English explanation)."""
    effective = model.strip() or default.strip() or 'large-v3-turbo'
    known = ALIASES.get(effective)
    if known is None:
        return 'unverified', f'{effective}: unverified custom model. Check its language and backend support before recording.'
    if known in ENGLISH and language != 'en':
        return 'incompatible', f'{effective} is English-only; it cannot transcribe {language}. Choose a multilingual model such as large-v3-turbo, or change the profile to English.'
    if language == 'yue' and known not in ENGLISH and known not in ('large', 'large-v3', 'large-v3-turbo', 'turbo'):
        return 'incompatible', f'{effective} has no Cantonese (yue) token. Choose large-v3 or large-v3-turbo.'
    return 'compatible', f'{effective}: known language support for {language}. Backend availability and download are not checked.'


def validate(language, model='', default=''):
    state, message = describe(language, model, default)
    if state == 'incompatible':
        raise ValueError(message)
