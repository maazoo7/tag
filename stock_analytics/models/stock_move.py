from odoo import api, models, fields
import json

import logging

_logger = logging.getLogger(__name__)

class StockMoveExt(models.Model):
    _inherit = "stock.move"
    _description = "Stock Move Extension"

    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account", string="Analytical Account",
                                          compute="_fleet_set_analytic")

    @api.depends("picking_id")
    def _fleet_set_analytic(self):
        for rec in self:
            if rec.picking_id.picking_type_id.code == 'internal' and rec.picking_id.fleet_id and rec.picking_id.fleet_id.analytic_account_id:
                rec.analytic_account_id = rec.picking_id.fleet_id.analytic_account_id.id
            else:
                rec.analytic_account_id = False

    def _get_account_move_line_vals(self):
        res = super()._get_account_move_line_vals()
        if self.analytic_account_id:
            payload = {self.analytic_account_id.id : 100.0}
            # analytic_distribution = json.dumps(payload)

            for entry in res:
                entry.update({
                    'analytic_distribution' : payload
                })
            _logger.info(f"analytic_account_id : {res}")
        return res



class FleetVehicleExt(models.Model):
    _inherit = "fleet.vehicle"

    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account", string="Analytical Account")
#
#
# class StockPickingExt(models.Model):
#     _inherit = "stock.picking"
#
#     @api.onchange('fleet_id')
#     def _onchange_fleet_set_analytic(self):
#         _logger.info(f"testssssss : {self.fleet_id} {self.picking_type_id.code}")
#         if self.fleet_id and self.picking_type_id.code == 'internal':
#                 _logger.info(f"testssssss : {self.fleet_id} {self.picking_type_id.code}")
#                 analytic = self.fleet_id.analytic_account_id
#                 self.move_line_ids.write({'analytic_account_id': analytic.id})
#



