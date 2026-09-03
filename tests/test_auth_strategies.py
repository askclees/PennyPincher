#!/usr/bin/env python3
"""Tests for FormAuthStrategy's username-field auto-detection against saved login-page HTML
fixtures. Needs a Playwright browser installed (`playwright install chromium`) since the
detection logic runs as in-page JS via Playwright, same as it does for real — these tests are
skipped if that's not available rather than failing the whole suite.
"""
import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crawler")
)

from pennypincher_crawler.auth.form_auth import _FIND_PASSWORD_JS, _FIND_USERNAME_JS  # noqa: E402

try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        p.chromium.launch(headless=True).close()
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False


PLAIN_FORM_HTML = """
<form id="login">
    <input type="text" id="user" name="user">
    <input type="password" id="pass" name="pass">
    <button type="submit">Log in</button>
</form>
"""

WRAPPED_FORM_HTML = """
<div class="login-box">
    <form>
        <div class="field"><label>Username</label><input type="text" name="username" /></div>
        <div class="field"><label>Password</label><input type="password" name="password" /></div>
        <div class="field"><input type="submit" value="Sign in"></div>
    </form>
</div>
"""

NO_USERNAME_FIELD_HTML = """
<form>
    <input type="password" name="password">
    <button type="submit">Log in</button>
</form>
"""

# Shaped after a real router's login page: a password-only form with a hidden honeypot password
# field (off-screen, tabindex="-1") ahead of the real one in DOM order.
HONEYPOT_FORM_HTML = """
<form>
    <div style="position: absolute; left: -9999px;">
        <input id="password-decoy" tabindex="-1" type="password" name="fake-password">
    </div>
    <input id="passwordInput" type="password" name="password">
    <button type="submit" disabled>Login</button>
</form>
"""


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "run `playwright install chromium` first")
class UsernameDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def _detect(self, html, password_selector="input[type=password]"):
        page = self.browser.new_page()
        try:
            page.set_content(html)
            return page.eval_on_selector(password_selector, _FIND_USERNAME_JS)
        finally:
            page.close()

    def test_plain_form_detects_id_selector(self):
        self.assertEqual(self._detect(PLAIN_FORM_HTML), "#user")

    def test_wrapped_form_detects_name_selector(self):
        self.assertEqual(self._detect(WRAPPED_FORM_HTML), '[name="username"]')

    def test_no_username_field_returns_none(self):
        self.assertIsNone(self._detect(NO_USERNAME_FIELD_HTML))


@unittest.skipUnless(PLAYWRIGHT_AVAILABLE, "run `playwright install chromium` first")
class PasswordDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def test_skips_honeypot_field_with_tabindex_minus_one(self):
        page = self.browser.new_page()
        try:
            page.set_content(HONEYPOT_FORM_HTML)
            selector = page.evaluate(_FIND_PASSWORD_JS)
        finally:
            page.close()
        self.assertEqual(selector, "#passwordInput")


if __name__ == "__main__":
    unittest.main()
