"""Real Qt interactions with an isolated simulated host; no mic or personal data.

Set QT_QPA_PLATFORM=offscreen for headless checks. Omit it for native GUI smoke.
Optional --screenshots DIR captures light/dark Languages and profile editor.
"""
import argparse
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from voice_to_clipboard.core.desktop_settings import load, validate
from voice_to_clipboard.core.settings import save_settings, read_settings
from voice_to_clipboard.ui.settings_window import SettingsWindow, style


def wait(app, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert predicate(), 'Timed out waiting for Settings'
    app.processEvents()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    style(app)
    windows = []
    with tempfile.TemporaryDirectory(prefix='vtc-qt-') as folder, patch.dict(os.environ,
            VOICE_TO_CLIPBOARD_DATA_DIR=folder, VOICE_TO_CLIPBOARD_CACHE_DIR=folder), \
            patch('voice_to_clipboard.platform.launchers.enabled', return_value=False):
        path = Path(folder) / 'settings.json'
        history = Path(folder) / 'history.json'
        fail = [False]
        malformed = [False]
        old_host = [False]
        calls = []
        def request(operation, **details):
            calls.append((operation, details))
            if operation == 'settings':
                time.sleep(.15)  # UI must wait for acknowledgement.
                if fail[0]:
                    fail[0] = False
                    raise RuntimeError('Shortcut registration conflict')
                save_settings(validate({**load(), **details['values']}))
                if malformed[0]:
                    malformed[0] = False
                    return {'state': 'listening'}
            if old_host[0]:
                return {'state': 'listening'}
            return dict(state='stopping' if operation == 'quit' else 'listening',
                        phase='idle', profiles=load()['profiles'], profile_modifiers=True,
                        onboarding_supported=True, onboarding_complete=load()['onboarding_complete'],
                        dictation_processes=0)
        def create():
            window = SettingsWindow(request)
            windows.append(window)
            window.show()
            wait(app, lambda: window.compatible)
            return window
        def dispose(window):
            window.forced_close = True
            window.close()
            window.shutdown()
        try:
            w = create()
            assert [p['language'] for p in w.settings['profiles']] == ['en']
            assert w.welcome.isVisible() and not path.exists()
            # Interrupted first run and Cancel are read-only.
            w.add_button.click()
            app.processEvents()
            e = w.editor
            e.language.setCurrentText('Polish (pl)')
            e.key.setText('P')
            e.cancel_button.click()
            app.processEvents()
            assert w.editor is None and not path.exists()
            dispose(w)
            w = create()
            w.edit_button.click()
            e = w.editor
            fail[0] = True
            e.save_button.click()
            wait(app, lambda: not w.pending)
            assert 'registration conflict' in e.feedback.text()
            assert not path.exists() and not load()['onboarding_complete']
            e.save_button.click()
            wait(app, lambda: not w.pending and w.editor is None)
            assert load()['onboarding_complete'] and not w.welcome.isVisible()
            # Preserve schema migration, history and unrelated fields.
            history.write_text('[{"text": "private sentinel"}]')
            save_settings({'unrelated': {'keep': True}})
            w.add_button.click()
            e = w.editor
            e.language.setCurrentText('Polish (pl)')
            e.key.setText('E')
            before = path.read_bytes()
            count = len(calls)
            e.save_button.click()
            assert 'already used' in e.errors['key'].text() and path.read_bytes() == before
            assert len(calls) == count
            e.key.setText('P')
            e.model.setCurrentText('tiny.en')
            e.save_button.click()
            assert 'English-only' in e.errors['model'].text() and path.read_bytes() == before
            e.model.setCurrentText('team/custom-model')
            e.modifiers.setCurrentText('ctrl+alt')
            e.delivery.setCurrentIndex(1)
            assert 'unverified custom model' in e.model_hint.text()
            fail[0] = True
            e.save_button.click()
            e.cancel_button.click()
            assert w.editor is e  # Cannot cancel a submitted transaction.
            wait(app, lambda: not w.pending)
            assert path.read_bytes() == before and e.key.text() == 'P'
            assert e.model.currentText() == 'team/custom-model'
            e.save_button.click()
            wait(app, lambda: w.editor is None)
            saved = load()
            assert saved['profiles'][1] == dict(language='pl', key='p', paste=True, model='team/custom-model', modifiers='alt+ctrl')
            assert read_settings()['unrelated'] == {'keep': True}
            assert history.read_text() == '[{"text": "private sentinel"}]'
            # Saving General never applies a draft in Advanced or vice versa.
            w.model.setCurrentText('tiny')
            w.overlay.setChecked(False)
            w.general_save.click()
            wait(app, lambda: not w.pending)
            assert load()['overlay'] is False and load()['model'] == ''
            assert w.model.currentText() == 'tiny'
            w.advanced_save.click()
            wait(app, lambda: not w.pending)
            assert load()['model'] == 'tiny' and not any(w.dirty())
            # Malformed save response leaves the draft open, polling recovers.
            w.edit_button.click()
            e = w.editor
            e.key.setText('A')
            malformed[0] = True
            e.save_button.click()
            wait(app, lambda: not w.pending)
            assert 'not confirmed' in e.feedback.text() and w.editor is e
            e.cancel_button.click()
            w.poll()
            wait(app, lambda: not w.poll_pending)
            assert w.settings['profiles'][0]['key'] == 'a'
            # An obsolete host cannot receive a settings mutation.
            old_host[0] = True
            w.poll()
            wait(app, lambda: not w.poll_pending)
            assert not w.compatible
            count = len([c for c in calls if c[0] == 'settings'])
            w.general_save.click()
            assert count == len([c for c in calls if c[0] == 'settings'])
            old_host[0] = False
            w.poll()
            wait(app, lambda: w.compatible)
            # Unsaved close is explicit; declined discard keeps the window.
            w.overlay.setChecked(True)
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
                w.close()
            assert w.isVisible()
            w.overlay.setChecked(False)
            # Removal is a single transaction and keeps one profile minimum.
            w.profiles.setCurrentRow(1)
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                w.remove_button.click()
            wait(app, lambda: not w.pending)
            assert len(load()['profiles']) == 1
            w.remove_button.click()
            assert 'at least one' in w.feedback.text()
            # Keyboard tab order, accessible field names, focus and native search.
            w.add_button.click()
            app.processEvents()
            e = w.editor
            e.activateWindow()
            wait(app, e.isActiveWindow)
            e.language.setFocus()
            wait(app, e.language.hasFocus)
            QTest.keyClick(e.language, Qt.Key.Key_Tab)
            assert e.key.hasFocus(), 'Tab must move from language to shortcut letter'
            QTest.keyClicks(e.key, 'P')
            e.language.lineEdit().selectAll()
            QTest.keyClicks(e.language.lineEdit(), 'Polish')
            assert e.language.completer().completionCount() == 1
            assert e.language.completer().currentCompletion() == 'Polish (pl)'
            e.language.completer().popup().hide()
            assert e.language.accessibleName() == 'Language'
            assert e.key.accessibleName() == 'Shortcut letter A–Z'
            for dark in (False, True):
                palette = app.palette()
                if not dark:
                    for role, color in [(QPalette.ColorRole.Window, '#f4f5f7'), (QPalette.ColorRole.Base, '#ffffff'),
                            (QPalette.ColorRole.Button, '#eef0f3'), (QPalette.ColorRole.Text, '#20252d'),
                            (QPalette.ColorRole.WindowText, '#20252d'), (QPalette.ColorRole.ButtonText, '#20252d'),
                            (QPalette.ColorRole.Mid, '#858d99'), (QPalette.ColorRole.Highlight, '#2867b2'),
                            (QPalette.ColorRole.HighlightedText, '#ffffff')]:
                        palette.setColor(role, QColor(color))
                if dark:
                    for role, color in [(QPalette.ColorRole.Window, '#20252d'), (QPalette.ColorRole.Base, '#171b22'),
                            (QPalette.ColorRole.Button, '#303742'), (QPalette.ColorRole.Text, '#f2f4f8'),
                            (QPalette.ColorRole.WindowText, '#f2f4f8'), (QPalette.ColorRole.ButtonText, '#f2f4f8'),
                            (QPalette.ColorRole.Highlight, '#416ca8'), (QPalette.ColorRole.HighlightedText, '#ffffff')]:
                        palette.setColor(role, QColor(color))
                app.setPalette(palette)
                app.processEvents()
                app.processEvents()
                assert e.save_button.isVisible() and e.cancel_button.isVisible()
                assert e.save_button.geometry().right() < e.width()
                assert e.height() <= e.screen().availableGeometry().height()
                assert e.key.palette().color(QPalette.ColorRole.Text).lightness() > 128 if dark else e.key.palette().color(QPalette.ColorRole.Text).lightness() < 128
                if args.screenshots:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    theme = 'dark' if dark else 'light'
                    w.grab().save(str(args.screenshots / f'languages-{theme}.png'))
                    e.grab().save(str(args.screenshots / f'editor-{theme}.png'))
            e.cancel_button.click()
            # External changes don't overwrite an open editor's baseline.
            w.edit_button.click()
            e = w.editor
            save_settings({'model': 'small'})
            w.poll()
            wait(app, lambda: not w.poll_pending)
            e.save_button.click()
            assert 'changed outside' in e.feedback.text()
            e.cancel_button.click()
            # Close during Save waits, successful acknowledgement closes it.
            w.overlay.setChecked(True)
            w.general_save.click()
            w.close()
            assert w.isVisible()
            wait(app, lambda: not w.isVisible())
            w.shutdown()
            w = create()
            assert load()['onboarding_complete'] and not w.welcome.isVisible()
            assert w.settings['model'] == 'small' and w.settings['overlay'] is True
            w.command('quit')
            wait(app, lambda: not w.isVisible())
            print('PASS: Qt first-run/resume, one Save, Cancel, conflicts, custom models, failure/retry, host compatibility, partial saves, remove, persistence, keyboard, themes and close/Quit')
        finally:
            for window in windows:
                dispose(window)


if __name__ == '__main__':
    main()
