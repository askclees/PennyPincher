from .base import AuthStrategy


class BasicAuthStrategy(AuthStrategy):
    """HTTP Basic Auth — credentials are supplied at the browser-context level, so there's no
    form to fill; Playwright answers the auth challenge itself during navigation.
    """

    def context_options(self):
        return {"http_credentials": {"username": self.username, "password": self.password}}

    async def login(self, page, base_url):
        await page.wait_for_load_state("networkidle")
