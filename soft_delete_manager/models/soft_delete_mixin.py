from odoo import models, fields

class SoftDeleteMixin(models.AbstractModel):
    _name = 'soft.delete.mixin'
    _description = 'Soft Delete Mixin'

    x_is_deleted = fields.Boolean(default=False)

    def unlink(self):
        for record in self:
            if hasattr(record, 'x_is_deleted'):
                record.x_is_deleted = True
            else:
                super(SoftDeleteMixin, self).unlink()
        return True
