function getAgentInfo(vm) {
    return vm?.$refs?.agentInfo;
}

export function showAgentNodeDetail(vm) {
    getAgentInfo(vm)?.showNodeDetail?.();
}

export function openAgentUpdateDialog(vm) {
    const agentInfo = getAgentInfo(vm);
    if (agentInfo?.selectedLiderNode?.type === "AHENK") {
        agentInfo.updateAgentConfirm = true;
    }
}

export function openAgentRenameDialog(vm) {
    const agentInfo = getAgentInfo(vm);
    if (!agentInfo?.selectedLiderNode || agentInfo.selectedLiderNode.type !== "AHENK") {
        return;
    }
    if (!agentInfo.selectedLiderNode.online) {
        agentInfo.$toast.add({
            severity: "warn",
            detail: vm.$t("computer.agent_info.rename_warn"),
            summary: vm.$t("computer.task.toast_summary"),
            life: 3000,
        });
        return;
    }
    agentInfo.renameAgentDialog = true;
    agentInfo.newHostname = "";
    agentInfo.validationRenameAgent = false;
}

export function openAgentMoveDialog(vm) {
    const agentInfo = getAgentInfo(vm);
    if (agentInfo?.selectedLiderNode?.type === "AHENK") {
        agentInfo.moveAgentDialog = true;
    }
}

export function openAgentDeleteDialog(vm) {
    const agentInfo = getAgentInfo(vm);
    if (agentInfo?.selectedLiderNode?.type === "AHENK") {
        agentInfo.deleteAgentConfirm = true;
    }
}

export function openFolderAddDialog(vm) {
    const agentInfo = getAgentInfo(vm);
    if (agentInfo?.selectedLiderNode?.type === "ORGANIZATIONAL_UNIT") {
        agentInfo.validationFolderName = false;
        agentInfo.folderName = "";
        agentInfo.addFolderDialog = true;
    }
}

export function openFolderDeleteDialog(vm) {
    const agentInfo = getAgentInfo(vm);
    if (agentInfo?.selectedLiderNode?.type === "ORGANIZATIONAL_UNIT") {
        agentInfo.deleteFolderDialog = true;
    }
}
