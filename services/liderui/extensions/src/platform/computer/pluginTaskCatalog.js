import { taskService } from "@/services/Task/TaskService.js";

function showPluginTaskToast(vm, detailKey) {
    vm.$toast.add({
        severity: "error",
        detail: vm.$t(detailKey),
        summary: vm.$t("computer.task.toast_summary"),
        life: 3000,
    });
}

export async function hydratePluginTaskState(vm, mapping = {}) {
    const { response, error } = await taskService.pluginTaskList();
    if (error) {
        showPluginTaskToast(vm, "computer.plugins.security.error_plugin_task_list");
        return false;
    }

    if (response.status === 417) {
        showPluginTaskToast(vm, "computer.plugins.security.error_417_plugin_task_list");
        return false;
    }

    if (response.status !== 200) {
        return false;
    }

    for (const entry of response.data || []) {
        const target = mapping[entry.page];
        if (!target) {
            continue;
        }
        vm[target.task] = entry;
        if (target.state) {
            vm[target.state] = entry.state;
        }
    }

    return true;
}
