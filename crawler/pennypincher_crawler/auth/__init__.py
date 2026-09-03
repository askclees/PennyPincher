from .basic_auth import BasicAuthStrategy
from .form_auth import FormAuthStrategy

STRATEGIES = {
    "form": FormAuthStrategy,
    "basic": BasicAuthStrategy,
}
