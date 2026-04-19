from odoo import api, models, fields
from odoo.exceptions import UserError
from datetime import timedelta, datetime

import logging

_logger = logging.getLogger(__name__)


class TaskChecklist(models.Model):
    _name = "task.checklist"
    _description = "task check list"

    name = fields.Char(string="Name")
    detail_description = fields.Text(string="Description")
    is_material_req = fields.Boolean(string="Material Requisition", default=False)
    active = fields.Boolean(string="Active", default=True)


class ProjectTaskInheritExt(models.Model):
    _inherit = "project.task"

    checklist_completed = fields.Boolean(string="Checklist Completed", compute="_compute_checklist_status", store=True)

    @api.model
    def create(self, vals):
        res = super(ProjectTaskInheritExt, self).create(vals)
        _logger.info(f"res id : {res.id}")
        task_checklist = self.env['task.checklist'].sudo().search([])
        task_activity_type = self.env['mail.activity.type'].sudo().search([('name', '=', 'To-Do')], limit=1)
        for task in res:
            for task_check in task_checklist:
                if not task_check.is_material_req:
                    activity_vals = {
                        'res_model': 'project.task',
                        'res_id': task.id,
                        'summary': task_check.name,
                        # 'date_deadline' : task_check.name,
                        'activity_type_id': task_activity_type.id,
                        'task_checklist_id': task_check.id,
                        'note': task_check.detail_description,
                        'user_id': self.env.user.id,
                        'res_model_id': self.env.ref('sale_project.model_project_task').id,
                    }
                    self.env['mail.activity'].create(activity_vals)
                else:
                    date_created = task.create_date
                    date_created = date_created - timedelta(days=30)
                    activity_vals = {
                        'res_model': 'project.task',
                        'res_id': task.id,
                        'summary': task_check.name,
                        'date_deadline' : date_created,
                        'activity_type_id': task_activity_type.id,
                        'task_checklist_id': task_check.id,
                        'note': task_check.detail_description,
                        'user_id': self.env.user.id,
                        'res_model_id': self.env.ref('sale_project.model_project_task').id,
                    }
                    self.env['mail.activity'].create(activity_vals)

        return res


    @api.depends("activity_ids.state")
    def _compute_checklist_status(self):
        for rec in self:
            activities = self.env['mail.activity'].sudo().with_context(active_test=False).search([
                ('res_model', '=', 'project.task'),
                ('res_id', '=', rec.id)
            ])

            if not activities:
                rec.checklist_completed = False
                continue
            for act in activities:
                _logger.info(f"activities : {act}")
                _logger.info(f"activities : {act.active}")
            _logger.info(f"all(activity.state== for activity in activities) {all(not activity.active for activity in activities)}")
            rec.checklist_completed = all(not activity.active for activity in activities)



    #todo update once done
    def write(self, vals):
        res = super(ProjectTaskInheritExt, self).write(vals)

        if 'planned_date_begin' in vals and vals['planned_date_begin']:
            planned_date = vals['planned_date_begin']
            if planned_date:
                if isinstance(planned_date, str):
                    try:
                        planned_date = datetime.strptime(planned_date, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        planned_date = datetime.strptime(planned_date, "%Y-%m-%d")

            planned_date = planned_date - timedelta(days=30)

            task_checklist_ids = self.env['task.checklist'].sudo().search([('is_material_req','=',True)])

            activities = self.env['mail.activity'].sudo().with_context(active_test=False).search([
                ('res_model', '=', 'project.task'),
                ('res_id', '=', self.id),
                ('task_checklist_id', 'in', task_checklist_ids.ids)
            ])


            for activity in activities:
                activity.write({
                    "date_deadline" : planned_date
                })

        if 'stage_id' in vals and vals['stage_id']:
            stage_id = self.env['project.task.type'].browse(vals['stage_id'])

            if stage_id.name.lower() == "done" and not self.checklist_completed:
                raise UserError("Please complete the related activities before marking the task as done")

        return res


class TaskActivityInherit(models.Model):
    _inherit = 'mail.activity'

    task_checklist_id = fields.Many2one(comodel_name="task.checklist", string="Task Checklist ID")

    def write(self, vals):
        res = super(TaskActivityInherit, self).write(vals)

        _logger.info(f"vals in mail activity : {vals}")

        return res

    def unlink(self):
        if self.res_model == "project.task":
            raise UserError("You cannot delete any activity related to Tasks")
        return super().unlink()
