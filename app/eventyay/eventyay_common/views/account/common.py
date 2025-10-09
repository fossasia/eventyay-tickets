from typing import Any

from ...navigation import get_account_navigation


class AccountMenuMixIn:
    def get_context_data(self, **kwargs) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx['nav_products'] = get_account_navigation(self.request)
        return ctx
