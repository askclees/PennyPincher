from abc import ABC, abstractmethod


class AuthStrategy(ABC):
    """Logs a Playwright page into a router admin UI before crawling begins.

    New router login mechanisms are added as new subclasses registered in
    `auth/__init__.py`'s STRATEGIES map — nothing else in the crawler needs to change.
    """

    def __init__(self, username, password, **options):
        self.username = username
        self.password = password
        self.options = options

    @abstractmethod
    async def login(self, page, base_url):
        """Perform login on `page` (already navigated to base_url). Must leave `page` on an
        authenticated page when it returns."""
        raise NotImplementedError

    def context_options(self):
        """Extra Playwright BrowserContext kwargs needed before the first navigation (e.g.
        http_credentials for Basic Auth). Applied once, at context creation."""
        return {}
