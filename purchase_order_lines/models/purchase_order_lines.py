import datetime

from odoo import api, models, fields

import logging

_logger = logging.getLogger(__name__)

class PurchaseOrderInheritExt(models.Model):
    _inherit = "purchase.order.line"

    actual_receive_date = fields.Date(
        string="Actual Receive Date",
        compute="_compute_actual_receive_date",
        store=True
    )

    status_color = fields.Char(
        compute="_compute_status_color",
        store=True
    )

    @api.depends('actual_receive_date', 'date_planned')
    def _compute_status_color(self):
        for line in self:
            line.status_color = ""
            if line.actual_receive_date and line.date_planned:

                actual_date = line.actual_receive_date.date() if isinstance(line.actual_receive_date,
                                                                            fields.Datetime) else line.actual_receive_date

                scheduled_date = line.date_planned.date() if isinstance(line.date_planned,
                                                                        datetime.datetime) else line.date_planned

                if actual_date > scheduled_date:
                    line.status_color = "red"
                else:
                    line.status_color = "green"

    @api.depends("move_ids", "move_ids.picking_id.date_done")
    def _compute_actual_receive_date(self):
        for line in self:
            done_pickings = line.move_ids.mapped("picking_id").filtered(
                lambda p: p.picking_type_id.code == "incoming" and p.date_done
            )

            if done_pickings:
                line.actual_receive_date = max(done_pickings.mapped("date_done")).date()
            else:
                line.actual_receive_date = False