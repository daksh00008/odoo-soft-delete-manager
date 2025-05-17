{
    'name': 'Soft Delete Manager',
    'version': '16.0.3.0.0',
    'summary': 'Manage soft delete functionality for Odoo models',
    'description': '''
        This module allows administrators to configure soft delete functionality
        for selected Odoo models. Features include:
        - Enabling soft delete for specific models.
        - Adding a "Recover Deleted" button on tree views.
        - A wizard to recover or permanently delete records.
        For more details, see the README file.
    ''',
    'category': 'Tools',
    'author': 'Daksh',
    'website': 'https://github.com/daksh00008',
    'license': 'OPL-1',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/soft_delete_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            "soft_delete_manager/static/src/js/soft_delete_tree_view_header_button.js",
            "soft_delete_manager/static/src/xml/soft_delete_tree_view_header_button.xml",
        ],
    },
    'images': [
        'static/description/soft_delete_manager_cover.png',
        # Add more images if you have screenshots
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
