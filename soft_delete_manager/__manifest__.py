{
    'name': 'Soft Delete Manager',
    'version': '16.0.2.0.0',  # Updated to include Odoo version 16.0
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
    'website': 'https://github.com/daksh00008',  # Replace with your website if available
    'license': 'AGPL-3',  # Added license (common for Odoo modules)
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
    'installable': True,
    'application': True,
    'auto_install': False,
}
