{
    'name': 'Stock Move',
    'version': '19.0.1.0.0',
    'category': 'Project',
    'summary': 'Checklist for tasks',
    'description': """
       Checklist for tasks
    """,
    'author': 'Team GalaxyITC',
    'website': 'https://www.galaxyitc.com',
    'depends': [
       'account'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_move.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}