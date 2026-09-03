from .base import AuthStrategy

DEFAULT_PASSWORD_SELECTOR = "input[type=password]"

# Picks the password field to fill when password_selector isn't given explicitly. Some login
# pages (observed on a real router) include a hidden decoy password input as an anti-bot
# honeypot — off-screen, tabindex="-1" so a real user's keyboard navigation never reaches it.
# Filling that one instead of the real field silently breaks the login, so this prefers a
# password field that's still in the normal tab order; only falls back to the first one on the
# page if every candidate looks like a honeypot.
_FIND_PASSWORD_JS = """
() => {
    const candidates = Array.from(document.querySelectorAll('input[type=password]'));
    if (!candidates.length) return null;
    const real = candidates.find((el) => el.tabIndex !== -1) || candidates[0];
    if (real.id) return `#${real.id}`;
    if (real.name) return `[name="${real.name}"]`;
    return null;
}
"""

# Finds the input immediately preceding the password field, in DOM order, within the same form
# (or the whole document if the password field isn't inside a <form>) — the common shape for a
# username/password login form even when field names/ids vary by router vendor. Routers with a
# password-only login (no username at all) simply have no candidate here, and this returns null.
_FIND_USERNAME_JS = """
(passwordEl) => {
    const scope = passwordEl.closest('form') || document;
    const inputs = Array.from(scope.querySelectorAll('input'));
    const pwIndex = inputs.indexOf(passwordEl);
    for (let i = pwIndex - 1; i >= 0; i--) {
        const el = inputs[i];
        const type = (el.type || 'text').toLowerCase();
        if (type === 'text' || type === 'email' || type === 'tel') {
            if (el.id) return `#${el.id}`;
            if (el.name) return `[name="${el.name}"]`;
        }
    }
    return null;
}
"""

# Some login forms (React/Vue-style) start the submit button disabled and only enable it once
# form validation reacts to the filled fields — clicking immediately after fill() can race that
# state update, so this polls briefly before clicking rather than assuming it's already enabled.
_SUBMIT_JS = """
async (passwordEl) => {
    const form = passwordEl.closest('form');
    if (!form) return false;
    const submit = form.querySelector(
        'button[type=submit], input[type=submit], button:not([type])'
    );
    if (!submit) return false;
    for (let i = 0; i < 20 && submit.disabled; i++) {
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    submit.click();
    return true;
}
"""


class FormAuthStrategy(AuthStrategy):
    """HTML form login, including password-only forms (no username field at all). Auto-detects
    the password/username fields and submit control by default; pass explicit CSS selectors
    (username_selector, password_selector, submit_selector) as extra options for routers whose
    login page defeats auto-detection (e.g. a login page with more than one password-type input,
    where the honeypot heuristic above guesses wrong).
    """

    async def login(self, page, base_url):
        explicit_password_selector = self.options.get("password_selector")
        username_selector = self.options.get("username_selector")
        submit_selector = self.options.get("submit_selector")

        await page.wait_for_selector(
            explicit_password_selector or DEFAULT_PASSWORD_SELECTOR, timeout=15000
        )

        password_selector = (
            explicit_password_selector
            or await page.evaluate(_FIND_PASSWORD_JS)
            or DEFAULT_PASSWORD_SELECTOR
        )

        if not username_selector:
            username_selector = await page.eval_on_selector(password_selector, _FIND_USERNAME_JS)

        if username_selector and self.username:
            await page.fill(username_selector, self.username)
        await page.fill(password_selector, self.password)

        if submit_selector:
            await page.click(submit_selector)
        else:
            clicked = await page.eval_on_selector(password_selector, _SUBMIT_JS)
            if not clicked:
                await page.keyboard.press("Enter")

        await page.wait_for_load_state("networkidle")
