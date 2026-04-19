# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'
    _description = 'Project Milestone'

    progress = fields.Float(
        string="Progress (%)",
        compute='_compute_progress',
    )

    progress_completion = fields.Float(string="Progress Completion")


    invoice_generated = fields.Boolean(string="Invoice Generated")

    @api.depends('task_ids')
    def _compute_progress(self):
        for rec in self:
            _logger.info(f"rec.task_ids {rec.task_ids}")
            total_task_count = len(rec.task_ids)
            for test in rec.task_ids:
                _logger.info(f"personal_stage_type_id {test.state}")
            if total_task_count > 0:

                completed_tasks = rec.task_ids.filtered(lambda t: t.stage_id.fold == True)
                completed_count = len(completed_tasks)
                rec.progress = (completed_count / total_task_count) * 100
                rec.progress_completion = rec.progress
                # rec.progress =
            else:
                rec.progress = 0
                rec.progress_completion = 0


    sale_order_id = fields.Many2one('sale.order', string='Sales Order', ondelete='restrict')

    start_date = fields.Datetime(
        string="Start Date",
        compute='_compute_start_date',
        # store=True,
        help="Date and time when the Milestone is planned to start. Computed from the earliest start date of all associated tasks."
    )

    @api.depends('task_ids.date_assign')
    def _compute_start_date(self):
        for milestone in self:
            tasks = milestone.task_ids

            for task in tasks:
                _logger.info(f"date start {task.planned_date_begin}")

            earliest_task = tasks.filtered(lambda t: t.planned_date_begin).sorted(key='planned_date_begin', reverse=False)[:1]
            _logger.info(f"earliest_task {earliest_task}")
            if earliest_task:
                milestone.start_date = earliest_task.planned_date_begin
                milestone.plan_start_date = earliest_task.planned_date_begin
            else:
                milestone.start_date = False  #
                milestone.plan_start_date = False  #

    end_date = fields.Datetime(
        string="End Date",
        compute='_compute_end_date',
        # store=True,
        help="Date and time when the Milestone is planned to finish. Computed from the latest end date (date_deadline) of all associated tasks."
    )

    plan_start_date = fields.Datetime(string="Plan Start Date")
    plan_end_date = fields.Datetime(string="Plan End Date")

    @api.depends('task_ids.date_deadline')
    def _compute_end_date(self):
        for milestone in self:
            tasks_with_deadline = milestone.task_ids.filtered(lambda t: t.date_deadline)

            latest_task = tasks_with_deadline.sorted(key='date_deadline', reverse=True)[:1]
            _logger.info(f"latest taskss ==== {latest_task}")

            if latest_task:
                milestone.end_date = latest_task.date_deadline
                milestone.plan_end_date = latest_task.date_deadline
            else:
                milestone.end_date = False
                milestone.plan_end_date = False

    percentage = fields.Float(string="Percentage")

    # def get_task_contribution(self):
    #     for rec in self:
    #         milestone_tasks = self.env['project.task'].sudo().search_count([('milestone_id','=',rec.id)])
    #         project_tasks = self.env['project.task'].sudo().search_count([('project_id','=',rec.project_id.id)])
    #         _logger.info(f"total milestones {milestone_tasks}")
    #         _logger.info(f"total project tasks {project_tasks}")
    #         if project_tasks > 0:
    #             rec.percentage = (milestone_tasks/project_tasks)*100
    #         else:
    #             rec.percentage = 0.0

    invoice_status = fields.Char(
        string="Invoice Status",
        compute="get_invoice_status",
        # store=True
    )

    @api.depends("progress", "invoice_generated")
    def get_invoice_status(self):
        for rec in self:
            if rec.progress >= 100 and rec.invoice_generated:
                rec.invoice_status = "Invoiced"
            elif rec.progress >= 100:
                rec.invoice_status = "Ready to Invoice"
            else:
                rec.invoice_status = "In Progress"


    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
        compute="_compute_total_amount",
        store=True
    )

    @api.depends('task_ids')
    def _compute_total_amount(self):
        milestone_price = 0
        for milestone in self:
            _logger.info(f"milestone {milestone}")
            _logger.info(f"milestone task_ids {milestone.task_ids}")
            project_id = milestone.task_ids.mapped('project_id')
            sale_order_id = self.env['sale.order'].sudo().search([('project_id','=',project_id.id)])
            all_product_links = milestone.task_ids.mapped('product_link_ids')
            all_product_links = all_product_links.mapped('product_id')
            _logger.info(f"all_product_links - {all_product_links}")
            _logger.info(f"sale_order_id - {sale_order_id}")
            for line in sale_order_id.order_line:
                _logger.info(f"Product {line.product_id}")
                if line.product_id and line.product_id.id in all_product_links.ids:
                    milestone_price += line.price_subtotal

            # total = sum(all_product_links.mapped('price_subtotal'))

            milestone.total_amount = milestone_price

    def create_invoice(self):
        for rec in self:
            _logger.info("=== Starting invoice generation for milestone ID %s ===", rec.id)
            if rec.progress_completion == 100 and rec.sale_order_id and not rec.invoice_generated:
                sale_order = rec.sale_order_id
                _logger.info("Related Sale Order: %s (ID: %s)", sale_order.name, sale_order.id)
                product_ids = rec.task_ids.mapped('product_link_ids.product_id')
                _logger.info("Products linked to milestone tasks: %s", product_ids.ids)

                if not product_ids:
                    _logger.warning("No products found for milestone %s tasks.", rec.name)
                    raise UserError(_("No products linked to tasks in this milestone."))

                linked_sale_lines = rec.task_ids.mapped('product_link_ids.sale_line_id')
                _logger.info("Sale lines linked to milestone tasks: %s", linked_sale_lines.ids)

                if not linked_sale_lines:
                    raise UserError(_("No sale order lines linked to tasks in this milestone."))

                lines_to_invoice = linked_sale_lines.filtered(lambda l: l.qty_to_invoice > 0)
                _logger.info("Invoiceable lines: %s", lines_to_invoice.ids)

                if not lines_to_invoice:
                    raise UserError(_("No invoiceable quantities found for milestone-linked sale order lines."))

                if not lines_to_invoice:
                    _logger.warning("No invoiceable quantities found for milestone %s products.", rec.name)
                    raise UserError(_("No invoiceable quantities found for milestone-related products."))

                invoice = self.env['account.move'].sudo().create({
                    'move_type': 'out_invoice',
                    'partner_id': sale_order.partner_invoice_id.id,
                    'partner_shipping_id': sale_order.partner_shipping_id.id,
                    'invoice_user_id': sale_order.user_id.id,
                    'team_id': sale_order.team_id.id,
                    'invoice_origin': sale_order.name,
                    'invoice_payment_term_id': sale_order.payment_term_id.id,
                    'fiscal_position_id': sale_order.fiscal_position_id.id,
                    'invoice_line_ids': [
                        (0, 0, {
                            'sale_line_ids': [(4, line.id)],
                            'product_id': line.product_id.id,
                            'name': line.name,
                            'quantity': line.qty_to_invoice,
                            'product_uom_id': line.product_uom_id.id,
                            'price_unit': line.price_unit,
                            'tax_ids': [(6, 0, line.tax_ids.ids)],
                            'discount': line.discount,
                            'analytic_distribution': line.analytic_distribution,
                        }) for line in lines_to_invoice
                    ],
                })

                _logger.info("Invoice created: %s (ID: %s)", invoice.name, invoice.id)

                # Post the invoice
                invoice.action_post()
                _logger.info("Invoice %s posted successfully.", invoice.name)

                # Mark milestone as invoiced
                rec.invoice_generated = True
                rec.message_post(body=_("Invoice %s created for milestone products." % invoice.name))

                _logger.info("Invoice created and milestone %s marked as invoiced.", rec.name)
                _logger.info("=== Invoice generation completed successfully for milestone ID %s ===", rec.id)

                # Redirect to invoice form view
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Customer Invoice'),
                    'res_model': 'account.move',
                    'view_mode': 'form',
                    'res_id': invoice.id,
                    'target': 'current',
                }

            _logger.info("No eligible milestones found for invoicing.")
            return True
