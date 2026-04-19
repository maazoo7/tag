{
    'name': 'Approval FLow for Project Task Deadline',
    'version': '19.0.1.0.0',
    'category': 'Project',
    'summary': 'Flow of Approval',
    'description': """
       Approval flow for project tasks
    """,
    'author': 'Team GalaxyITC',
    'website': 'https://www.galaxyitc.com',
    'depends': [
       'project'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/project_task_deadline_management.xml'
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}