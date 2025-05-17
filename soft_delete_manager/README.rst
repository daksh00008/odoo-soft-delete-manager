Soft Delete Manager
==================

Overview
--------
This module enables soft delete functionality for selected Odoo models. Instead of permanently deleting records, they are marked as deleted and can be recovered or permanently removed using a wizard.

Features
--------
- Configure soft delete for specific Odoo models via settings.
- Adds a "Recover Deleted" button to tree views of configured models.
- Provides a wizard to recover or permanently delete soft-deleted records.
- Ensures soft-deleted records are hidden from default views using domain filters.

Installation
------------
1. Download or clone this module into your Odoo addons directory.
2. Update the Apps list in Odoo (Apps > Update Apps List).
3. Search for "Soft Delete Manager" and install the module.
4. Configure the models for soft delete under Settings > Soft Delete Manager.

Usage
-----
1. After installation, go to **Settings > Soft Delete Manager**.
2. Select the models for which you want to enable soft delete.
3. Save the settings. The selected models will now have a soft delete feature:
   - Deleting a record will mark it as soft-deleted.
   - A "Recover Deleted" button will appear in the tree view to access deleted records.
4. Use the wizard to either recover or permanently delete records.

Support
-------
For issues or support, please contact the author at [your email] or open an issue on GitHub: https://github.com/daksh00008/soft_delete_manager.

License
-------
This module is licensed under the AGPL-3 license.
