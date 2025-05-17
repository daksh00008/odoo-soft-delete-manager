from odoo import models, fields, api, _
import logging
from lxml import etree

_logger = logging.getLogger(__name__)

class SoftDeleteConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    model_ids = fields.Many2many(
        'ir.model',
        string="Model Name",
        domain="[('model', '!=', False)]",
        related='config_id.model_ids',
        readonly=False
    )

    config_id = fields.Many2one(
        'soft.delete.manager.config',
        string="Configuration",
        required=True,
        default=None
    )

    def set_values(self):
        super().set_values()
        self.ensure_one()
        previous_model_ids = self.config_id.model_ids.ids
        new_model_ids = self.model_ids.ids
        _logger.info(f"Saving Soft Delete configuration: previous_model_ids={previous_model_ids}, new_model_ids={new_model_ids}")

        self.config_id.write({'model_ids': [(6, 0, new_model_ids)]})
        self._apply_soft_delete(new_model_ids, previous_model_ids)
        self.env.cr.commit()

        IrModel = self.env['ir.model']
        IrUiView = self.env['ir.ui.view']
        IrModelData = self.env['ir.model.data']
        IrActionsServer = self.env['ir.actions.server']

        # Remove outdated inherited views
        existing_views = IrUiView.search([
            ('inherit_id.model', 'in', [m.model for m in IrModel.search([])]),
            ('name', '=', 'soft_delete_manager.tree.view.inherit.dynamic')
        ])
        existing_views.unlink()

        # Process each model
        for model in IrModel.browse(new_model_ids):
            # Add js_class to tree view
            tree_view = IrUiView.search([
                ('model', '=', model.model),
                ('type', '=', 'tree'),
                ('mode', '=', 'primary')
            ], limit=1)

            if tree_view:
                xml_id_record = IrModelData.search([
                    ('model', '=', 'ir.ui.view'),
                    ('res_id', '=', tree_view.id)
                ], limit=1)
                inherit_id_ref = xml_id_record.complete_name if xml_id_record else False

                # Parse the arch_db string into an XML tree
                try:
                    parser = etree.XMLParser(remove_blank_text=True)
                    tree = etree.fromstring(tree_view.arch_db, parser=parser)
                    current_js_class_nodes = tree.xpath("//tree/@js_class")
                    current_js_class = current_js_class_nodes[0] if current_js_class_nodes else ""
                except etree.ParseError as e:
                    _logger.error(f"Failed to parse XML for view {tree_view.id} of model {model.model}: {str(e)}")
                    current_js_class = ""

                new_js_class = current_js_class
                if "soft_delete_manager_list_view_with_button" not in current_js_class:
                    if current_js_class:
                        new_js_class = f"{current_js_class},soft_delete_manager_list_view_with_button"
                    else:
                        new_js_class = "soft_delete_manager_list_view_with_button"

                IrUiView.create({
                    'name': 'soft_delete_manager.tree.view.inherit.dynamic',
                    'model': model.model,
                    'type': 'tree',
                    'inherit_id': tree_view.id,
                    'mode': 'extension',
                    'arch': f"""
                        <xpath expr="//tree" position="attributes">
                            <attribute name="js_class">{new_js_class}</attribute>
                        </xpath>
                    """
                })
                _logger.info(f"Added js_class to tree view of model {model.model} (inherit_id: {tree_view.id}, external ref: {inherit_id_ref}, new js_class: {new_js_class})")
            else:
                _logger.warning(f"No primary tree view found for model {model.model}")

            # Create wizard model and views
            wizard_model_name = self._create_dynamic_wizard_model_and_view(model.model)

            # Ensure server action exists
            self._ensure_server_action(model, wizard_model_name)

        self._apply_domain_to_actions(new_model_ids)

    def _ensure_server_action(self, model, wizard_model_name):
        """Ensure a server action exists for the given wizard model."""
        IrActionsServer = self.env['ir.actions.server']
        wizard_class_name = wizard_model_name.replace('.', '_')
        action_name = f"Populate {wizard_class_name} Records"

        _logger.debug(f"Checking for server action '{action_name}' for model {model.model}")
        existing_server_action = IrActionsServer.search([
            ('name', '=', action_name),
            ('model_id.model', '=', model.model),
        ], limit=1)

        if not existing_server_action:
            IrActionsServer.create({
                'name': action_name,
                'model_id': model.id,
                'state': 'code',
                'code': f"""
                    env['soft.delete.manager.config'].populate_wizard_records('{model.model}', '{wizard_model_name}')
                """,
            })
            _logger.info(f"Created server action '{action_name}' for model {model.model}")
        else:
            _logger.info(f"Server action '{action_name}' already exists for model {model.model} (ID: {existing_server_action.id})")

    @api.model
    def ensure_all_server_actions(self):
        """Ensure server actions exist for all configured models."""
        config = self._get_or_create_config()
        IrModel = self.env['ir.model']
        for model in config.model_ids:
            wizard_model_name = f"x_{model.model.replace('.', '_')}_wizard"
            if not IrModel.search([('model', '=', wizard_model_name)], limit=1):
                _logger.warning(f"Wizard model {wizard_model_name} does not exist, creating it")
                self._create_dynamic_wizard_model_and_view(model.model)
            self._ensure_server_action(model, wizard_model_name)
        _logger.info("Verified server actions for all configured models")

    def _apply_domain_to_actions(self, model_ids):
        IrModel = self.env['ir.model']
        IrModelData = self.env['ir.model.data']
        IrActionsActWindow = self.env['ir.actions.act_window']

        for model in IrModel.browse(model_ids):
            action = IrActionsActWindow.search([
                ('res_model', '=', model.model),
                ('view_mode', 'in', ['tree,form', 'form,tree'])
            ], limit=1)

            if action:
                action.write({
                    'domain': "[('x_is_deleted', '=', False)]"
                })
                xml_id_record = IrModelData.search([
                    ('model', '=', 'ir.actions.act_window'),
                    ('res_id', '=', action.id)
                ], limit=1)
                if xml_id_record:
                    _logger.info(f"Updated domain for action {xml_id_record.module}.{xml_id_record.name} of model {model.model}")
                else:
                    _logger.info(f"Updated domain for action (no XML ID) of model {model.model}")
            else:
                _logger.warning(f"No action found for model {model.model}")

    def _apply_soft_delete(self, new_model_ids, previous_model_ids):
        return self.env['soft.delete.manager.config']._apply_soft_delete(new_model_ids, previous_model_ids)

    @api.model
    def get_values(self):
        res = super(SoftDeleteConfigSettings, self).get_values()
        config = self._get_or_create_config()
        self.ensure_all_server_actions()
        res['config_id'] = config.id
        res['model_ids'] = [(6, 0, config.model_ids.ids)]
        return res

    @api.model
    def _get_or_create_config(self):
        config = self.env['soft.delete.manager.config'].search([], limit=1)
        if not config:
            config = self.env['soft.delete.manager.config'].create({})
        return config

    def _create_dynamic_wizard_model_and_view(self, model_name):
        IrModel = self.env['ir.model']
        IrModelFields = self.env['ir.model.fields']
        IrUiView = self.env['ir.ui.view']
        IrActionsServer = self.env['ir.actions.server']

        wizard_model_name = f"x_{model_name.replace('.', '_')}_wizard"
        wizard_class_name = wizard_model_name.replace('.', '_')

        existing_model = IrModel.search([('model', '=', wizard_model_name)], limit=1)
        if existing_model:
            _logger.info(f"Wizard model {wizard_model_name} already exists.")
            return wizard_model_name

        wizard_model = IrModel.create({
            'name': wizard_class_name,
            'model': wizard_model_name,
            'state': 'manual'
        })

        for field_data in [
            {
                'name': 'x_model_id',
                'field_description': 'Screen Name',
                'ttype': 'many2one',
                'relation': 'ir.model',
                'domain': "[('model', '!=', False)]",
                'readonly': True,
            },
            {
                'name': 'x_record_id',
                'field_description': 'Original Record ID',
                'ttype': 'integer',
                'readonly': True,
            },
            {
                'name': 'x_display_name',
                'field_description': 'Name',
                'ttype': 'char',
                'readonly': True,
            },
        ]:
            existing_field = IrModelFields.search([
                ('model', '=', wizard_model_name),
                ('name', '=', field_data['name'])
            ], limit=1)
            if not existing_field:
                field_data.update({
                    'model_id': wizard_model.id,
                    'model': wizard_model_name,
                    'state': 'manual',
                })
                IrModelFields.create(field_data)
                _logger.info(f"Created field '{field_data['name']}' for model: {wizard_model_name}")
            else:
                _logger.info(f"Field '{field_data['name']}' already exists for model: {wizard_model_name}")

        IrUiView.create({
            'name': f'{wizard_model_name}.form',
            'model': wizard_model_name,
            'arch': f'''
                <form string="{wizard_class_name}">
                    <sheet>
                        <group>
                            <field name="x_model_id"/>
                            <field name="x_record_id"/>
                            <field name="x_display_name"/>
                        </group>
                    </sheet>
                </form>
            ''',
            'type': 'form'
        })

        restore_action_name = f"Restore {wizard_class_name} Records"
        existing_restore_action = IrActionsServer.search([
            ('name', '=', restore_action_name),
            ('model_id.model', '=', wizard_model_name),
        ], limit=1)

        if not existing_restore_action:
            restore_action = IrActionsServer.create({
                'name': restore_action_name,
                'model_id': wizard_model.id,
                'state': 'code',
                'code': f"""
                    env['soft.delete.manager.config'].restore_records('{model_name}', records.mapped('x_record_id'))
                """,
            })
            _logger.info(f"Created restore server action '{restore_action_name}' for wizard {wizard_model_name}")
        else:
            restore_action = existing_restore_action
            _logger.info(f"Using existing restore server action '{restore_action_name}' for wizard {wizard_model_name}")

        delete_action_name = f"Permanent Delete {wizard_class_name} Records"
        existing_delete_action = IrActionsServer.search([
            ('name', '=', delete_action_name),
            ('model_id.model', '=', wizard_model_name),
        ], limit=1)

        if not existing_delete_action:
            delete_action = IrActionsServer.create({
                'name': delete_action_name,
                'model_id': wizard_model.id,
                'state': 'code',
                'code': f"""
                    env['soft.delete.manager.config'].permanent_delete_records('{model_name}', records.mapped('x_record_id'))
                """,
            })
            _logger.info(f"Created permanent delete server action '{delete_action_name}' for wizard {wizard_model_name}")
        else:
            delete_action = existing_delete_action
            _logger.info(f"Using existing permanent delete server action '{delete_action_name}' for wizard {wizard_model_name}")

        IrUiView.create({
            'name': f'{wizard_model_name}.tree',
            'model': wizard_model_name,
            'arch': f'''
                <tree string="{wizard_class_name}" create="false" edit="false" delete="false">
                    <header>
                        <button name="{restore_action.id}" string="Restore" type="action" icon="fa-undo" confirm="Are you sure you want to restore the selected records?"/>
                        <button name="{delete_action.id}" string="Permanent Delete" type="action" icon="fa-trash" confirm="Are you sure you want to permanently delete the selected records?"/>
                    </header>
                    <field name="x_model_id"/>
                    <field name="x_record_id" invisible="1"/>
                    <field name="x_display_name"/>
                </tree>
            ''',
            'type': 'tree'
        })

        _logger.info(f"Created wizard and views for model: {wizard_model_name}")
        return wizard_model_name