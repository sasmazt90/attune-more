"""Operational upgrade checks must respect preserved preferences instead of a seeded German fixture."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('upgrade_preferences', Path(__file__).resolve().parents[2] / 'scripts/qa/realistic/apk_upgrade_check.py')
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)


class Page:
    def __init__(self, stored, visible=None):
        self.stored = stored
        self.visible = visible or stored
        self.script_calls = []
    def goto(self, *args, **kwargs): pass
    def wait_for_function(self, *args): pass
    def wait_for_timeout(self, *args): pass
    def screenshot(self, **kwargs): pass
    def evaluate(self, script):
        self.script_calls.append(script)
        assert 'setItem' not in script and 'removeItem' not in script
        return 200 if 'fetch(' in script else {'language': self.stored, 'region': 'İstanbul'}
    def locator(self, selector):
        page = self
        class Locator:
            def input_value(self): return page.visible if selector == '#attune-language' else 'İstanbul'
            def inner_text(self): return {'tr': 'Sağlık modülleri', 'en': 'Health modules', 'de': 'Gesundheitsmodule'}[page.visible]
            def count(self): return 1 if selector == 'main' else 0
            def evaluate_all(self, script): return []
            @property
            def first(self): return self
        return Locator()


@pytest.mark.parametrize('language', ['tr', 'en', 'de'])
def test_preserved_language_and_nonfixture_region_are_accepted(language, tmp_path):
    page = Page(language)
    checks = upgrade.operational(page, tmp_path, 'after', [])
    assert all(row['passed'] for row in checks)


def test_visible_language_mismatch_is_reported_without_rewriting_preference(tmp_path):
    checks = upgrade.operational(Page('en', 'de'), tmp_path, 'after', [])
    assert [row['check'] for row in checks if not row['passed']] == ['The chosen language is still in use']


def test_native_socket_selection_ignores_external_browser_and_stale_sockets():
    sockets = '@webview_devtools_remote_1234\n@webview_devtools_remote_123\n@webview_devtools_remote_999'
    assert upgrade.native_webview_socket(sockets, '123\n') == 'webview_devtools_remote_123'
    assert upgrade.native_webview_socket(sockets, '12') is None
    assert upgrade.native_webview_socket(sockets, '') is None
    assert upgrade.native_webview_socket(sockets, '123 999') is None
