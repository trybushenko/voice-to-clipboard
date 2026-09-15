"""Install UK/EN shortcuts; --no-overlay reverts only the overlay experiment."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import shutil
import shlex
base = 'org.gnome.settings-daemon.plugins.media-keys'
schema = base + '.custom-keybinding:'
root = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/'
def get(target, key):
    return ast.literal_eval(subprocess.check_output(['gsettings', 'get', target, key], text=True).strip())
def put(target, key, value):
    subprocess.run(['gsettings', 'set', target, key, repr(value)], check=True)
def main():
    paths = get(base, 'custom-keybindings')
    en = root + 'dictate-english/'
    old = root + 'dictate-format/'
    for path in paths:
        if path != en and get(schema + path, 'binding') in ('<Shift><Alt>e', '<Alt><Shift>e'):
            raise SystemExit('Alt+Shift+E already assigned; no changes made')
    backup = Path(__file__).resolve().parents[1] / 'backups' / 'shortcuts.before-overlay.json'
    backup.parent.mkdir(exist_ok=True)
    if not backup.exists():
        backup.write_text(json.dumps({p: {k: get(schema+p,k) for k in ('name','command','binding')} for p in paths}, indent=2))
    flag = '' if '--no-overlay' in sys.argv else ' --overlay'
    executable = shutil.which('dictate')
    exe = (shlex.quote(executable) if executable else shlex.join([sys.executable, str(Path(__file__).resolve().parents[1] / 'dictate.py')])) + ' --silence 0'
    for name, lang, extra in [('custom1','uk',''), ('custom2','uk',' --paste')]:
        target = schema + root + name + '/'
        if 'Dictate' not in get(target,'name'):
            raise SystemExit('Unexpected shortcut owner')
        put(target,'command',exe+' --lang '+lang+extra+flag)
    for key, value in [('name','Dictate English'),('binding','<Shift><Alt>e'),('command',exe+' --lang en --beam 5'+flag)]:
        put(schema+en,key,value)
    paths = [p for p in paths if p != old]
    if en not in paths:
        paths.append(en)
    put(base,'custom-keybindings',paths)
    subprocess.run(['gsettings','reset-recursively',schema+old],check=True)
    for path in [root+'custom1/',root+'custom2/',en]:
        print(get(schema+path,'binding'),get(schema+path,'command'))
    assert old not in get(base,'custom-keybindings')


if __name__ == "__main__":
    main()
