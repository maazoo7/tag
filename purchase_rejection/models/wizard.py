from odoo import models, fields

class PurchaseOrderRejectionReason(models.Model):
    _name = 'purchase.order.rejection.reason'
    _description = 'PO Rejection Reason'

    name = fields.Char(string='Reason', required=True)
    description = fields.Text(string='Description')



class PurchaseOrderRejectWizard(models.TransientModel):
    _name = 'purchase.order.reject.wizard'
    _description = 'Wizard for rejecting PO'

    reason_id = fields.Many2one('purchase.order.rejection.reason', string='Reason', required=True)
    description = fields.Text(string='Description')
    po_id = fields.Many2one('purchase.order', string='Purchase Order')

    def action_reject(self):
        self.po_id.write({'state': 'rejected'})

        message = (
            "Purchase Order rejected.\n"
            "Reason : %s\n"
            "Description : %s"
        ) % (self.reason_id.name, self.description or '-')

        self.po_id.message_post(body=message)
