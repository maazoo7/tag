from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskExt(models.Model):
    _inherit = "project.task"

    is_date_plan_set = fields.Boolean(string="Plan Date Set")
    is_deadline_set = fields.Boolean(string="Date Deadline Set")
    is_progamatic_change = fields.Boolean(string="Progamatic Change")
    total_change_requests = fields.Char(string="Change Requests", compute="_get_total_requests")


    def _get_total_requests(self):
        for rec in self:
            total_req = self.env['project.date.change.request'].search_count([('task_id','=',rec.id)])
            rec.total_change_requests = total_req


    def write(self, vals):
        # res = super().write(vals)

        _logger.info(f"Valssss in taskkkkkk : {vals}")
        if self.is_date_plan_set and self.is_deadline_set and ('planned_date_begin' in vals or 'date_deadline' in vals) and not self.is_progamatic_change:
            raise ValidationError("Changing the Dates of the task need approval please send a request for approval")

        if 'planned_date_begin' in vals and vals['planned_date_begin']:
            self.is_date_plan_set = True
        if 'date_deadline' in vals and vals['date_deadline']:
            self.is_deadline_set = True


        return super().write(vals)

    def action_view_linked_change_req(self):
        action = self.env['ir.actions.act_window']._for_xml_id('task_deadline_approval.action_project_date_change_req')

        action['display_name'] = _("%(name)s's Change Requests", name=self.name)

        action['domain'] = [('task_id', '=', self.id)]

        action['context'] = {'default_task_id': self.id}

        return action




class RequestDateChange(models.TransientModel):
    _name = 'date.change.wizard'
    _description = 'Change date of Task'

    task_id = fields.Many2one(comodel_name="project.task",string="Task ID")
    reason = fields.Char(string="Reason")
    prev_date_begin = fields.Datetime(string="Previous Date Start")
    new_date_begin = fields.Datetime(string="New Date Start", required=True)
    prev_date_deadline = fields.Datetime(string="Previous Date Deadline")
    new_date_deadline = fields.Datetime(string="New Date Deadline",  required=True)



    def action_change_dates(self):
        for rec in self:
            vals = {
                'task_id' : rec.task_id.id,
                'reason' : rec.reason,
                'state' : 'draft',
                'prev_date_begin' : rec.prev_date_begin,
                'new_date_begin' : rec.new_date_begin,
                'prev_date_deadline' : rec.prev_date_deadline,
                'new_date_deadline' : rec.new_date_deadline,
            }
            self.env['project.date.change.request'].create(vals)
            message = f"Request to change the dates of task {rec.task_id.name} is submitted for approval"
            rec.task_id.message_post(body=message)



class ProjectDateChangeReq(models.Model):
    _name = "project.date.change.request"
    _description = "Project date change request"

    task_id = fields.Many2one(comodel_name="project.task", string="Task ID")
    reason = fields.Char(string="Reason")
    prev_date_begin = fields.Datetime(string="Previous Date Start")
    new_date_begin = fields.Datetime(string="New Date Start")
    prev_date_deadline = fields.Datetime(string="Previous Date Deadline")
    new_date_deadline = fields.Datetime(string="New Date Deadline")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Approved'),
        ('reject', 'Rejected'),
    ])


    def action_approve(self):
        for rec in self:
            rec.state = 'done'
            rec.task_id.is_progamatic_change = True
            rec.task_id.sudo().write({
                'planned_date_begin' : rec.new_date_begin,
                'date_deadline' : rec.new_date_deadline,
            })
            rec.task_id.is_progamatic_change = False
            message = f"The request to change the dates is approved"
            rec.task_id.message_post(body=message)

    def action_reject(self):
        for rec in self:
            rec.state = 'reject'
            message = f"The request to change the dates is rejected"
            rec.task_id.message_post(body=message)

    def action_reset(self):
        for rec in self:
            rec.state = 'draft'

