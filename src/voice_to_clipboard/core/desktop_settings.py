"""Validated settings shared by the tray controller and settings panel."""
from .settings import read_settings
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
    return result


def load():
    return validate(read_settings())


def arguments():
    settings = load()
    result = ['--inference-device', settings['inference_device']]
    if settings['model']:
        result += ['--model', settings['model']]
    if not settings['overlay']:
        result.append('--no-overlay')
    return result
