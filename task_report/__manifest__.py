{
    'name': 'Project Tasks',
    'version': '19.0.1.0.0',
    'category': 'Project',
    'summary': 'Checklist for tasks',
    'description': """
       Checklist for tasks
    """,
    'author': 'Team GalaxyITC',
    'website': 'https://www.galaxyitc.com',
    'depends': [
       'base', 'sale_project'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/task.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}