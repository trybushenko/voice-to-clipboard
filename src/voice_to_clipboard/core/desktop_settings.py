"""Validated settings shared by the tray controller and settings panel."""
from .settings import read_settings
from . import profiles
from ..platform.windows_hotkeys import parse_modifiers

DEFAULTS = {'hotkey_modifiers': 'alt+shift', 'model': '', 'inference_device': 'auto', 'overlay': True}


def validate(values):
    if not isinstance(values, dict):
        raise ValueError('Settings must be an object')
    result = {name: values.get(name, default) for name, default in DEFAULTS.items()}
    if not isinstance(result['hotkey_modifiers'], str):
        raise ValueError('Choose hotkey modifiers')
    parse_modifiers(result['hotkey_modifiers'])
    result['hotkey_modifiers'] = result['hotkey_modifiers'].lower()
    if not isinstance(result['model'], str) or len(result['model']) > 300:
        raise ValueError('Model must be a name or path of at most 300 characters')
    if result['inference_device'] not in ('auto', 'cpu', 'cuda', 'metal'):
        raise ValueError('Choose auto, cpu, cuda or metal')
    if type(result['overlay']) is not bool:
        raise ValueError('Overlay must be enabled or disabled')
    if values.get('schema_version', 2) != 2:
        raise ValueError('Unsupported settings version; upgrade the app before editing')
    result['profiles'] = profiles.validate(values.get('profiles', profiles.defaults()))
    result['schema_version'] = 2
    for profile in result['profiles']:
        model = profile['model'] or result['model']
        if profile['language'] != 'en' and model.endswith('.en'):
            raise ValueError('English-only model selected for a non-English profile')
    return result


def load():
    values = read_settings()
    if 'profiles' not in values:
        from ..platform.paths import data_dir
        legacy = bool(values) or (data_dir() / 'history.json').exists()
        values = {**values, 'profiles': profiles.defaults(legacy)}
    return validate(values)


def arguments():
    settings = load()
    result = ['--inference-device', settings['inference_device']]
    if settings['model']:
        result += ['--model', settings['model']]
    if not settings['overlay']:
        result.append('--no-overlay')
    return result
