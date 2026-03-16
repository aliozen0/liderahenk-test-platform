import { computerManagementService } from "@/services/ComputerManagement/ComputerManagement.js";

function buildCounts(total, online) {
    return {
        total,
        online,
        offline: total - online,
    };
}

function showAgentCountToast(vm, detailKey) {
    vm.$toast.add({
        severity: "error",
        detail: vm.$t(detailKey),
        summary: vm.$t("computer.task.toast_summary"),
        life: 3000,
    });
}

export async function fetchAgentCounts(vm, node) {
    if (node?.type === "AHENK") {
        return buildCounts(1, node.online ? 1 : 0);
    }

    const params = new FormData();
    params.append(
        "searchDn",
        node?.type === "ORGANIZATIONAL_UNIT" ? node.distinguishedName : "agents"
    );

    const { response, error } = await computerManagementService.computerAgentListSize(params);
    if (error) {
        showAgentCountToast(vm, "computer.agent_info.error_agent_list_size");
        return null;
    }

    if (response.status === 417) {
        showAgentCountToast(vm, "computer.agent_info.error_417_agent_list_size");
        return null;
    }

    if (response.status !== 200) {
        return null;
    }

    return buildCounts(response.data.agentListSize, response.data.onlineAgentListSize);
}
