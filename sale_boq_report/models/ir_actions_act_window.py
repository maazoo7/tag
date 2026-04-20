# -*- coding: utf-8 -*-
from odoo import models


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    def _register_hook(self):
        """Normalize legacy action contexts that rely on undefined `active_ids`.

        Some actions are configured with a context expression similar to:
            {'default_res_model': 'purchase.order', 'default_res_ids': active_ids}
        When opened from a menu (without selection context), `active_ids` is not
        available in the JS evaluator and crashes the client.
        """
        result = super()._register_hook()

        actions = self.search(
            [
                ("context", "!=", False),
                ("context", "like", "default_res_model"),
                ("context", "like", "purchase.order"),
                ("context", "like", "default_res_ids"),
                ("context", "like", "active_ids"),
            ]
        )
        for action in actions:
            original = action.context or ""
            patched = original
            patched = patched.replace(
                "'default_res_ids': active_ids",
                "'default_res_ids': context.get('active_ids', [])",
            )
            patched = patched.replace(
                '"default_res_ids": active_ids',
                '"default_res_ids": context.get(\'active_ids\', [])',
            )
            if patched != original:
                action.context = patched

        return result
