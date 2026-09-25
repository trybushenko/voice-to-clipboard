"""Qt Settings client. All persistence and shortcut mutations belong to the host."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from PySide6.QtCore import Qt, QTimer, QObject, QEvent
from PySide6.QtWidgets import (QCheckBox, QComboBox, QCompleter,
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QScrollArea, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget)

from ..core.desktop_settings import load, validate
from ..core.profiles import LANGUAGE_NAMES, language_options, language_code, saved_profiles
from ..core.model_compatibility import CHOICES, describe, validate as validate_model
from ..platform.windows_hotkeys import parse_modifiers


def label(text):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def combo(name, values, value='', editable=True):
    widget = QComboBox()
    widget.setAccessibleName(name)
    widget.setEditable(editable)
    widget.addItems(values)
    widget.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    widget.setCurrentText(value)
    return widget


def fit_window(widget, width, height):
    available = widget.screen().availableGeometry()
    widget.resize(min(width, available.width() - 32), min(height, available.height() - 48))


def button(text, action):
    widget = QPushButton(text)
    widget.clicked.connect(action)
    return widget


class PaletteRefresh(QObject):
    """Repolish palette-based style rules when the OS changes appearance."""
    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() == QEvent.Type.ApplicationPaletteChange:
            QTimer.singleShot(0, self.refresh)
        return False

    def refresh(self):
        app = self.parent()
        app.setStyleSheet(app.styleSheet())


def style(app):
    # System palette supplies light/dark and high-contrast colours; Qt handles DPI.
    app.setStyle('Fusion')
    if not hasattr(app, '_palette_refresh'):
        app._palette_refresh = PaletteRefresh(app)
        app.installEventFilter(app._palette_refresh)
    app.setStyleSheet('''
        QWidget { font-size: 14px; color: palette(window-text); }
        QScrollArea { border: none; }
        QLabel#heading { font-size: 25px; font-weight: 600; }
        QPushButton { padding: 8px 14px; border: 1px solid palette(mid);
                      border-radius: 6px; background: palette(button); }
        QPushButton:hover { border-color: palette(highlight); }
        QPushButton:focus, QLineEdit:focus, QComboBox:focus, QListWidget:focus,
        QCheckBox:focus, QTabBar::tab:focus { border: 2px solid palette(highlight); }
        QPushButton:disabled { color: palette(mid); }
        QLineEdit, QComboBox { padding: 7px; border: 1px solid palette(mid); border-radius: 5px; }
        QListWidget { border: 1px solid palette(mid); border-radius: 8px; padding: 6px; }
        QListWidget::item { padding: 14px 8px; }
        QListWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }
        QTabBar::tab { padding: 10px 18px; }
        QTabBar::tab:selected { border-bottom: 3px solid palette(highlight); }
    ''')


class ProfileEditor(QDialog):
    def __init__(self, window, index=None):
        super().__init__(window)
        self.window = window
        self.index = index
        self.baseline = deepcopy(window.settings)
        self.pending = False
        self.setWindowTitle('Add language' if index is None else 'Edit language')
        self.setModal(True)
        fit_window(self, 560, 680)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)
        title = label(self.windowTitle())
        title.setObjectName('heading')
        outer.addWidget(title)
        outer.addWidget(label('Choose a language, a shortcut and where your words go.'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        form = QFormLayout(body)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setSpacing(10)
        p = self.baseline['profiles'][index] if index is not None else dict(language='en', key='', paste=False, model='')
        self.language = combo('Language', language_options(), f"{LANGUAGE_NAMES[p['language']]} ({p['language']})")
        self.language.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.language.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.language.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.key = QLineEdit(p['key'].upper())
        self.key.setAccessibleName('Shortcut letter A–Z')
        self.key.setPlaceholderText('A–Z')
        self.modifiers = combo('Profile modifiers', ['', 'alt+shift', 'ctrl+alt', 'ctrl+alt+shift'], p.get('modifiers', ''))
        self.modifiers.lineEdit().setPlaceholderText('Use default: ' + self.baseline['hotkey_modifiers'])
        self.delivery = combo('Delivery', ['Clipboard', 'Paste into original field'],
                              'Paste into original field' if p['paste'] else 'Clipboard', False)
        self.model = combo('Model override', CHOICES, p['model'])
        self.model.lineEdit().setPlaceholderText('Use default: ' + (self.baseline['model'] or 'large-v3-turbo'))
        self.errors = {}
        for name, caption, widget in [('language', '&Language (type to search)', self.language),
                ('key', 'Shortcut &letter A–Z', self.key), ('modifiers', '&Modifiers (empty = default)', self.modifiers),
                ('delivery', '&Delivery', self.delivery), ('model', 'Model &override (optional)', self.model)]:
            form.addRow(caption, widget)
            error = label('')
            error.setAccessibleName(caption.replace('&', '') + ' error')
            error.hide()
            form.addRow(error)
            self.errors[name] = error
        form.addRow(label('Paste is guarded: if the original field cannot be verified, text stays in the clipboard.'))
        self.body = body
        self.model_hint = label('')
        form.addRow(self.model_hint)
        self.language.currentTextChanged.connect(self.model_feedback)
        self.model.currentTextChanged.connect(self.model_feedback)
        self.feedback = label('')
        self.feedback.setAccessibleName('Save result')
        outer.addWidget(self.feedback)
        self.actions = QDialogButtonBox()
        self.save_button = self.actions.addButton('Save' if self.baseline['onboarding_complete'] else 'Save and finish setup', QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_button = self.actions.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.save_button.clicked.connect(self.save)
        self.cancel_button.clicked.connect(self.reject)
        outer.addWidget(self.actions)
        self.model_feedback()
        self.language.setFocus()

    def model_feedback(self):
        try:
            code = language_code(self.language.currentText())
            self.model_hint.setText(describe(code, self.model.currentText(), self.baseline['model'])[1])
        except ValueError:
            self.model_hint.setText('Choose a supported language from the search results.')

    def field_error(self, name, message):
        self.errors[name].setText(message)
        self.errors[name].show()
        getattr(self, name).setAccessibleDescription(message)
        getattr(self, name).setFocus()

    def save(self):
        if self.pending:
            return
        for name, error in self.errors.items():
            error.hide()
            getattr(self, name).setAccessibleDescription('')
        try:
            code = language_code(self.language.currentText())
        except ValueError as exc:
            self.field_error('language', str(exc))
            return
        key = self.key.text().strip().lower()
        if len(key) != 1 or key not in 'abcdefghijklmnopqrstuvwxyz':
            self.field_error('key', 'Choose one letter A–Z.')
            return
        profiles = deepcopy(self.baseline['profiles'])
        if any(p['key'] == key for i, p in enumerate(profiles) if i != self.index):
            self.field_error('key', 'This letter is already used. Choose a different letter.')
            return
        modifiers = self.modifiers.currentText().strip()
        try:
            if modifiers:
                parse_modifiers(modifiers)
        except ValueError as exc:
            self.field_error('modifiers', str(exc))
            return
        model = self.model.currentText().strip()
        try:
            if len(model) > 300:
                raise ValueError('Model names and paths must be at most 300 characters.')
            validate_model(code, model, self.baseline['model'])
        except ValueError as exc:
            self.field_error('model', str(exc))
            return
        profile = dict(language=code, key=key, modifiers=modifiers, model=model, paste=self.delivery.currentIndex() == 1)
        if self.index is None:
            profiles.append(profile)
        else:
            profiles[self.index] = profile
        if self.window.settings != self.baseline:
            self.feedback.setText('Settings changed outside this editor. Cancel and reopen the profile before saving.')
            return
        self.window.save_patch({'schema_version': 3, 'profiles': profiles, 'onboarding_complete': True}, self)

    def reject(self):
        if not self.pending:
            super().reject()

    def closeEvent(self, event):
        if self.pending:
            event.ignore()
        else:
            event.accept()


class SettingsWindow(QWidget):
    def __init__(self, request, control=None):
        super().__init__()
        self.request = request
        self.control = control
        self.settings = load()
        self.compatible = False
        self.pending = False
        self.close_after_save = False
        self.forced_close = False
        self.editor = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='settings-ipc')
        self.jobs = []
        self.poll_pending = False
        self.misses = 0
        self.setWindowTitle('Voice to Clipboard — Settings')
        fit_window(self, 760, 650)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)
        heading = label('Settings')
        heading.setObjectName('heading')
        outer.addWidget(heading)
        self.status = label('Connecting to Voice to Clipboard…')
        self.status.setAccessibleName('Application status')
        outer.addWidget(self.status)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)
        languages, layout = self.page('Languages')
        self.welcome = label('Welcome. Choose your language, shortcut and clipboard or paste. Save a profile to finish setup. No microphone test or model download runs here.')
        layout.addWidget(self.welcome)
        self.profiles = QListWidget()
        self.profiles.setWordWrap(True)
        self.profiles.setAccessibleName('Language profiles: language, shortcut, delivery')
        self.profiles.itemActivated.connect(lambda unused: self.edit_profile())
        layout.addWidget(self.profiles, 1)
        row = QHBoxLayout()
        self.add_button = button('Add &language', lambda: self.edit_profile(add=True))
        self.edit_button = button('&Edit', self.edit_profile)
        self.remove_button = button('&Remove', self.remove_profile)
        for widget in (self.add_button, self.edit_button, self.remove_button):
            row.addWidget(widget)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(label('Press your shortcut to start dictation, then press it again to stop. Closing Settings keeps the tray app running.'))
        general, layout = self.page('General')
        self.overlay = QCheckBox('Show recording overlay')
        layout.addWidget(self.overlay)
        self.general_save = button('Save General', lambda: self.save_patch({'overlay': self.overlay.isChecked()}))
        layout.addWidget(self.general_save)
        from ..platform.launchers import enabled
        self.auto = QCheckBox('Start at login (current user only)')
        self.auto.setChecked(enabled())
        self.auto.clicked.connect(self.autostart)
        layout.addWidget(self.auto)
        layout.addWidget(label('Login startup takes effect immediately. Appearance follows your system theme.'))
        layout.addStretch()
        advanced, layout = self.page('Advanced')
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.modifiers = combo('Default shortcut modifiers', ['alt+shift', 'ctrl+alt', 'ctrl+alt+shift'])
        self.model = combo('Default model', CHOICES)
        self.model.lineEdit().setPlaceholderText('Multilingual large-v3-turbo')
        self.device = combo('Inference device', ['auto', 'cpu', 'cuda', 'metal'], 'auto', False)
        form.addRow('Default shortcut &modifiers', self.modifiers)
        form.addRow('Default &model (empty = multilingual turbo)', self.model)
        form.addRow('Inference &device', self.device)
        layout.addLayout(form)
        layout.addWidget(label('Profiles inherit these defaults unless they have an override. Model language checks run before saving; downloads and backend availability are not checked here.'))
        self.advanced_save = button('Save Advanced', self.save_advanced)
        layout.addWidget(self.advanced_save)
        layout.addStretch()
        diagnostics, layout = self.page('Diagnostics')
        self.report = QTextEdit('System check does not record audio or download models.')
        self.report.setReadOnly(True)
        self.report.setAccessibleName('System check results')
        layout.addWidget(self.report, 1)
        row = QHBoxLayout()
        row.addWidget(button('Check system', self.check_system))
        row.addWidget(button('Open log', self.open_log))
        layout.addLayout(row)
        # These remain available when Linux has no tray host.
        row = QHBoxLayout()
        for caption, operation in [('Pause shortcuts', 'pause'), ('Resume', 'resume'), ('Quit app', 'quit')]:
            row.addWidget(button(caption, partial(self.command, operation)))
        layout.addLayout(row)
        self.feedback = label('')
        self.feedback.setAccessibleName('Settings save result')
        outer.addWidget(self.feedback)
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll)
        self.poll_timer.start(1000)
        self.poll()

    def page(self, name):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        scroll.setWidget(body)
        self.tabs.addTab(scroll, name)
        return body, layout

    def submit(self, operation, callback, failed=None, **details):
        if len(self.jobs) >= 16:
            message = 'Busy; wait for the current operation and try again.'
            if failed:
                failed(message)
            else:
                self.feedback.setText(message)
            return
        self.jobs.append((self.executor.submit(self.request, operation, **details), callback, failed))

    def task(self, function, callback):
        if len(self.jobs) >= 16:
            self.feedback.setText('Busy; wait for the current operation and try again.')
            return False
        self.jobs.append((self.executor.submit(function), callback, None))
        return True

    def tick(self):
        if self.control:
            self.control.dispatch(self.control_request)
        for job in list(self.jobs):
            future, callback, failed = job
            if future.done():
                self.jobs.remove(job)
                try:
                    callback(future.result())
                except Exception as exc:
                    if failed:
                        failed(str(exc))
                    else:
                        self.feedback.setText(str(exc))

    def control_request(self, payload):
        if payload.get('op') == 'quit':
            self.forced_close = True
            self.close()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()  # Only an explicit Settings/show request.
        return {'ok': True}

    def poll(self):
        if not self.poll_pending and not self.pending and len(self.jobs) < 16:
            self.poll_pending = True
            self.submit('status', self.received, self.status_error)

    def status_error(self, message):
        self.poll_pending = False
        self.compatible = False
        self.misses += 1
        self.status.setText('Host unavailable: ' + message)
        if self.misses >= 2:
            self.forced_close = True
            self.close()

    def received(self, value):
        self.poll_pending = False
        self.misses = 0
        self.compatible = False
        try:
            profiles = saved_profiles(value)
            if value.get('profile_modifiers') is not True or value.get('onboarding_supported') is not True:
                raise RuntimeError('Quit the tray app and relaunch the updated app before saving Settings.')
            self.compatible = True
            self.status.setText(f"{value.get('phase', 'idle').capitalize()} · Shortcuts {value.get('state', 'unknown')}\n{value.get('message', '')}".strip())
            current = load()
            current['profiles'] = profiles
            if current != self.settings and not self.pending:
                self.refresh(current)
        except (ValueError, RuntimeError) as exc:
            self.status.setText(str(exc))

    def refresh(self, settings=None):
        general_dirty, advanced_dirty = self.dirty()
        if settings is not None:
            self.settings = settings
        if not general_dirty:
            self.overlay.setChecked(self.settings['overlay'])
        if not advanced_dirty:
            self.modifiers.setCurrentText(self.settings['hotkey_modifiers'])
            self.model.setCurrentText(self.settings['model'])
            self.device.setCurrentText(self.settings['inference_device'])
        selected = max(0, self.profiles.currentRow())
        self.profiles.clear()
        for p in self.settings['profiles']:
            modifiers = p.get('modifiers') or self.settings['hotkey_modifiers']
            inherited = ' · default modifiers' if not p.get('modifiers') else ''
            self.profiles.addItem(f"{LANGUAGE_NAMES[p['language']]}    {modifiers}+{p['key'].upper()}{inherited}\n{'Paste into original field' if p['paste'] else 'Clipboard'}")
        self.profiles.setCurrentRow(min(selected, self.profiles.count() - 1))
        self.welcome.setVisible(not self.settings['onboarding_complete'])
        self.edit_button.setText('&Edit' if self.settings['onboarding_complete'] else '&Set up language')

    def dirty(self):
        # Widgets are initialized once before the first refresh.
        if not hasattr(self, '_loaded'):
            self._loaded = True
            return False, False
        return (self.overlay.isChecked() != self.settings['overlay'],
                self.advanced_values() != {k: self.settings[k] for k in ('hotkey_modifiers', 'model', 'inference_device')})

    def advanced_values(self):
        return dict(hotkey_modifiers=self.modifiers.currentText(), model=self.model.currentText().strip(), inference_device=self.device.currentText())

    def edit_profile(self, add=False):
        if self.pending:
            return
        self.editor = ProfileEditor(self, None if add else self.profiles.currentRow())
        self.editor.finished.connect(self.editor_finished)
        self.editor.open()

    def editor_finished(self, result):
        editor = self.editor
        self.editor = None
        if editor:
            editor.deleteLater()

    def remove_profile(self):
        if self.pending:
            return
        if len(self.settings['profiles']) == 1:
            self.feedback.setText('Keep at least one language profile. Edit it to change your language.')
            return
        index = self.profiles.currentRow()
        if QMessageBox.question(self, 'Remove language', 'Remove this profile and its shortcut?') != QMessageBox.StandardButton.Yes:
            return
        profiles = deepcopy(self.settings['profiles'])
        del profiles[index]
        self.save_patch({'profiles': profiles})

    def save_advanced(self):
        self.save_patch(self.advanced_values())

    def save_patch(self, patch, editor=None):
        feedback = editor.feedback if editor else self.feedback
        if not self.compatible:
            feedback.setText('Waiting for a compatible host. Quit the tray app and relaunch after updating if this persists.')
            return
        if self.pending:
            return
        try:
            validate({**self.settings, **patch})
        except ValueError as exc:
            feedback.setText(str(exc))
            return
        self.pending = True
        self.tabs.setEnabled(False)
        if editor:
            editor.pending = True
            editor.actions.setEnabled(False)
            editor.body.setEnabled(False)
        feedback.setText('Saving and registering shortcuts…')
        def finish():
            self.pending = False
            self.tabs.setEnabled(True)
            if editor:
                editor.pending = False
                editor.actions.setEnabled(True)
                editor.body.setEnabled(True)
        def failed(message):
            finish()
            self.close_after_save = False
            feedback.setText('Save not confirmed: ' + message + ' Your input is kept; check the host and retry.')
            if editor and any(word in message.lower() for word in ('shortcut', 'hotkey', 'register')):
                editor.field_error('key', message)
        def saved(value):
            profiles = saved_profiles(value)
            if patch.get('onboarding_complete') and value.get('onboarding_complete') is not True:
                raise RuntimeError('Setup was not confirmed; quit the tray app and relaunch the updated app.')
            current = load()
            current['profiles'] = profiles
            finish()
            self.refresh(current)
            if 'overlay' in patch:
                self.overlay.setChecked(current['overlay'])
            if 'hotkey_modifiers' in patch:
                self.modifiers.setCurrentText(current['hotkey_modifiers'])
                self.model.setCurrentText(current['model'])
                self.device.setCurrentText(current['inference_device'])
            self.feedback.setText('Saved and active. Shortcuts remain available after closing Settings.')
            if editor:
                editor.accept()
            if self.close_after_save:
                self.close_after_save = False
                self.close()
        # Partial updates preserve unsaved edits in other pages and unrelated preferences.
        self.submit('settings', saved, failed, values=deepcopy(patch))

    def autostart(self):
        from ..platform.launchers import enabled, set_enabled
        desired = self.auto.isChecked()
        self.auto.setEnabled(False)
        def change():
            error = ''
            try:
                set_enabled(desired)
            except Exception as exc:
                error = str(exc)
            return enabled(), error
        def completed(result):
            actual, error = result
            self.auto.setEnabled(True)
            self.auto.setChecked(actual)
            self.feedback.setText(error or ('Login startup enabled.' if actual else 'Login startup disabled.'))
        if not self.task(change, completed):
            self.auto.setEnabled(True)
            self.auto.setChecked(not desired)

    def check_system(self):
        from ..platform.diagnostics import report
        self.task(report, self.report.setPlainText)

    def open_log(self):
        from .desktop_panel import open_log
        self.task(open_log, lambda unused: None)

    def command(self, operation):
        def completed(value):
            if operation == 'quit':
                self.status.setText('Finishing dictation and exiting…')
                if not value.get('dictation_processes'):
                    self.forced_close = True
                    self.close()
            else:
                self.received(value)
        self.submit(operation, completed)

    def closeEvent(self, event):
        if not self.forced_close:
            if self.pending:
                self.close_after_save = True
                self.feedback.setText('Waiting for Save before closing…')
                event.ignore()
                return
            if any(self.dirty()) and QMessageBox.question(self, 'Unsaved settings', 'Discard unsaved General or Advanced changes?') != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.timer.stop()
        self.poll_timer.stop()
        event.accept()

    def shutdown(self):
        self.timer.stop()
        self.poll_timer.stop()
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.jobs.clear()  # Release UI callbacks only on the GUI thread.
