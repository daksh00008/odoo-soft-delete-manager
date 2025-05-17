/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { useService } from "@web/core/utils/hooks";

export class SoftDeleteManagerListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        console.info("SoftDeleteManagerListController initialized", {
            model: this.props.resModel,
        });
    }

    async onRecoverClick() {
        console.log("Recover button clicked");
        const modelName = this.props.resModel;
        // Replace all dots with underscores
        const wizardModelName = `x_${modelName.replace(/\./g, '_')}_wizard`;
        console.info("Preparing to populate wizard records", {
            modelName,
            wizardModelName,
        });

        try {
            // Find the server action
            const serverActions = await this.orm.searchRead(
                'ir.actions.server',
                [['name', '=', `Populate ${wizardModelName} Records`]],
                ['id'],
                { limit: 1 }
            );

            if (!serverActions.length) {
                console.error("Server action not found", {
                    actionName: `Populate ${wizardModelName} Records`,
                    wizardModelName,
                    modelName,
                });
                this.notification.add(
                    `Server action 'Populate ${wizardModelName} Records' not found. Please ensure the model '${modelName}' is configured in Soft Delete Manager settings.`,
                    { type: "danger", sticky: true }
                );
                return;
            }

            const serverActionId = serverActions[0].id;
            console.info("Found server action", { serverActionId, wizardModelName });

            // Execute the server action
            await this.orm.call('ir.actions.server', 'run', [serverActionId]);
            console.info("Wizard records populated successfully", { wizardModelName });

            // Capitalize model name for display (e.g., "cargo.short.name.master" -> "Cargo Short Name Master")
            const displayModelName = modelName
                .split('.')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');

            // Open the wizard with dynamic name
            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                name: `${displayModelName} Recover Deleted Records`,
                res_model: wizardModelName,
                view_mode: 'tree',
                views: [[false, 'tree']],
                target: 'current',
                domain: [['x_model_id.model', '=', modelName]],
            });
            console.log("Action triggered to open wizard", { wizardModelName, displayName: `${displayModelName} Recover Deleted Records` });
        } catch (err) {
            console.error("Error in onRecoverClick", {
                error: err.message || err,
                modelName,
                wizardModelName,
            });
            this.notification.add(
                `You are not allowed to access this function: ${err.message || "Unknown error"}`,
                { type: "danger", sticky: true }
            );
        }
    }
}

registry.category("views").add('soft_delete_manager_list_view_with_button', {
    ...listView,
    Model: listView.Model,
    Renderer: listView.Renderer,
    Controller: SoftDeleteManagerListController,
    buttonTemplate: "soft_delete_manager.ListView.Buttons.SoftDelete",
    viewModel: listView.viewModel,
});