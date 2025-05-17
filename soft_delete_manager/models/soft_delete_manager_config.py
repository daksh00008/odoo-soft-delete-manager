from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import time
import psycopg2

_logger = logging.getLogger(__name__)

class SoftDeleteManagerConfig(models.Model):
    _name = 'soft.delete.manager.config'
    _description = 'Soft Delete Manager Configuration'

    model_ids = fields.Many2many('ir.model', string="Model Names", domain="[('model', '!=', False)]")

    def write(self, vals):
        """Override write to add x_is_deleted field and apply custom unlink method to newly selected models."""
        previous_model_ids = self.model_ids.ids
        res = super(SoftDeleteManagerConfig, self).write(vals)
        if 'model_ids' in vals:
            new_model_ids = self.model_ids.ids
            self._apply_soft_delete(new_model_ids, previous_model_ids)
            self._apply_custom_unlink(new_model_ids)
        return res

    def _apply_soft_delete(self, new_model_ids, previous_model_ids):
        """Add x_is_deleted field to newly selected models and apply action domain."""
        IrModel = self.env['ir.model']
        IrModelFields = self.env['ir.model.fields']
        new_models = IrModel.browse(new_model_ids).filtered(lambda m: m.id not in previous_model_ids)

        _logger.info(f"🔧 Applying soft delete to {len(new_models)} models: {[m.model for m in new_models]}")

        for model in new_models:
            # Check if field already exists
            existing_field = IrModelFields.search([
                ('model', '=', model.model),
                ('name', '=', 'x_is_deleted')
            ], limit=1)

            if existing_field:
                _logger.warning(f"⚠️ x_is_deleted field already exists in model {model.model}, skipping.")
                continue

            # Create x_is_deleted field
            IrModelFields.create({
                'name': 'x_is_deleted',
                'model_id': model.id,
                'model': model.model,
                'field_description': 'Soft Deleted',
                'ttype': 'boolean',
                'store': True,
            })
            _logger.info(f"✅ Created x_is_deleted field in {model.model}")

            # Ensure database column exists
            table_name = model.model.replace('.', '_')
            self.env.cr.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'x_is_deleted'
            """, (table_name,))
            column_exists = self.env.cr.fetchone()

            if not column_exists:
                self.env.cr.execute(f"""
                    ALTER TABLE "{table_name}"
                    ADD COLUMN x_is_deleted BOOLEAN DEFAULT FALSE
                """)
                _logger.info(f"🗃️ Added x_is_deleted column to table {table_name}")
            else:
                self.env.cr.execute(f"""
                    ALTER TABLE "{table_name}"
                    ALTER COLUMN x_is_deleted SET DEFAULT FALSE
                """)
                _logger.info(f"🔁 Updated x_is_deleted column to default FALSE in {table_name}")

            self.env.cr.commit()

        # Apply action domain to ensure soft-deleted records are not shown in tree views
        self._apply_action_domain(new_model_ids)

    def _apply_action_domain(self, model_ids):
        """Apply domain to actions to exclude soft-deleted records in tree views."""
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

    def _apply_custom_unlink(self, model_ids):
        """Dynamically patch the unlink method of the given models."""
        for model_id in model_ids:
            model = self.env['ir.model'].browse(model_id)
            if model:
                self._patch_unlink_method(model.model)

    def _patch_unlink_method(self, model_name):
        """Dynamically patch the unlink method for the given model."""
        try:
            model_cls = self.env[model_name].__class__

            # Check if already patched to avoid infinite recursion
            if hasattr(model_cls, '_soft_delete_patched') and model_cls._soft_delete_patched:
                _logger.info(f"🔒 unlink already patched for {model_name}, skipping.")
                return

            original_unlink = getattr(model_cls, 'unlink', None)
            if not original_unlink:
                _logger.warning(f"No unlink method found for {model_name}, skipping patching.")
                return

            # Store the original unlink method
            setattr(model_cls, 'unlink_original', original_unlink)

            def patched_unlink(self):
                """Modified unlink method to perform soft delete."""
                _logger.debug(f"Executing patched unlink for model {model_name} on records: {self.ids}")
                for record in self:
                    if 'x_is_deleted' in record._fields:
                        if not record.x_is_deleted:  # Only update if not already deleted
                            record.write({'x_is_deleted': True})
                            _logger.info(f"Soft-deleted record ID {record.id} in model {model_name}")
                        else:
                            _logger.debug(f"Record ID {record.id} in model {model_name} already soft-deleted")
                    else:
                        _logger.warning(f"x_is_deleted field not found in {model_name}, falling back to original unlink for record ID {record.id}")
                        original_unlink(record)
                return True

            model_cls.unlink = patched_unlink
            model_cls._soft_delete_patched = True
            _logger.info(f"✅ Patched unlink method for model: {model_name}")
        except Exception as e:
            _logger.error(f"Failed to patch unlink method for {model_name}: {str(e)}")
            raise

    @api.model
    def populate_wizard_records(self, model_name, wizard_model_name):
        """Populate wizard records for soft-deleted records of the given model."""
        _logger.info(f"Populating wizard records for model: {model_name}, wizard: {wizard_model_name}")
        try:
            model = self.env[model_name]
            deleted_records = model.with_context(active_test=False).search([('x_is_deleted', '=', True)])

            wizard_model = self.env[wizard_model_name]
            ir_model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)

            if not ir_model:
                _logger.error(f"No ir.model record found for model: {model_name}")
                raise ValueError(f"Model {model_name} not found in ir.model")

            # Remove wizard records for non-deleted or non-existent records
            existing_wizards = wizard_model.search([('x_model_id', '=', ir_model.id)])
            for wiz in existing_wizards:
                record = model.browse(wiz.x_record_id)
                if not record.exists() or not record.x_is_deleted:
                    wiz.unlink()

            records_to_create = []
            for record in deleted_records:
                existing_wizard = wizard_model.search([
                    ('x_model_id', '=', ir_model.id),
                    ('x_record_id', '=', record.id),
                ], limit=1)

                if not existing_wizard:
                    records_to_create.append({
                        'x_model_id': ir_model.id,
                        'x_record_id': record.id,
                        'x_display_name': record.display_name if hasattr(record, 'display_name') else str(record.id),
                    })
                    _logger.debug(f"Prepared wizard record for {model_name} (ID: {record.id})")

            if records_to_create:
                wizard_model.create(records_to_create)
                _logger.info(f"Created {len(records_to_create)} wizard records for {wizard_model_name}")
            else:
                _logger.info(f"No new wizard records to create for {wizard_model_name}")

        except Exception as e:
            _logger.error(f"Failed to populate wizard records for {model_name}, wizard: {wizard_model_name}: {str(e)}")
            raise

    @api.model
    def restore_records(self, model_name, record_ids):
        try:
            records = self.env[model_name].browse(record_ids)
            recovered_count = len(records)
            records.write({'x_is_deleted': False})
            _logger.info(f"Restored {recovered_count} records in model {model_name}")

            # Remove corresponding wizard records
            wizard_model_name = f"x_{model_name.replace('.', '_')}_wizard"
            self.env[wizard_model_name].search([
                ('x_model_id.model', '=', model_name),
                ('x_record_id', 'in', record_ids)
            ]).unlink()

            return True
        except Exception as e:
            _logger.error(f"Failed to restore records for {model_name}: {str(e)}")
            raise

    @api.model
    def permanent_delete_records(self, model_name, record_ids):
        """Permanently delete records and remove corresponding wizard records."""
        try:
            records = self.env[model_name].browse(record_ids)
            deleted_count = len(records)
            records.unlink_original()  # Call original unlink to perform hard delete
            _logger.info(f"Permanently deleted {deleted_count} records in model {model_name}")

            # Remove corresponding wizard records
            wizard_model_name = f"x_{model_name.replace('.', '_')}_wizard"
            self.env[wizard_model_name].search([
                ('x_model_id.model', '=', model_name),
                ('x_record_id', 'in', record_ids)
            ]).unlink()

            return True
        except Exception as e:
            _logger.error(f"Failed to permanently delete records for {model_name}: {str(e)}")
            raise