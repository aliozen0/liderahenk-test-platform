export function buildComputerContextMenu({ t, node, invokeAction }) {
    switch (node.type) {
        case "ORGANIZATIONAL_UNIT": {
            const items = [
                {
                    label: t("computer.agent_info.node_detail"),
                    icon: "pi pi-list",
                    command: () => invokeAction("showNodeDetail"),
                },
                {
                    label: t("computer.agent_info.add_folder"),
                    icon: "pi pi-folder-open",
                    command: () => invokeAction("openAddFolder"),
                },
            ];
            if (!node.isRoot) {
                items.push({
                    label: t("computer.agent_info.delete_folder"),
                    icon: "pi pi-trash",
                    command: () => invokeAction("openDeleteFolder"),
                });
            }
            return items;
        }
        case "AHENK":
        case "WIND0WS_AHENK":
            return [
                {
                    label: t("computer.agent_info.node_detail"),
                    icon: "pi pi-list",
                    command: () => invokeAction("showNodeDetail"),
                },
                {
                    label: t("computer.agent_info.update"),
                    icon: "pi pi-refresh",
                    command: () => invokeAction("openUpdateAgent"),
                },
                {
                    label: t("computer.agent_info.rename"),
                    icon: "pi pi-pencil",
                    command: () => invokeAction("openRenameAgent"),
                },
                {
                    label: t("computer.agent_info.move_agent"),
                    icon: "el-icon-rank",
                    command: () => invokeAction("openMoveAgent"),
                },
                {
                    label: t("computer.agent_info.delete_client"),
                    icon: "pi pi-trash",
                    command: () => invokeAction("openDeleteAgent"),
                },
            ];
        default:
            return [];
    }
}

export function positionComputerContextMenu(menuElement, event) {
    if (!menuElement) {
        return;
    }
    menuElement.style.top = `${event.clientY}px`;
    menuElement.style.left = `${event.clientX}px`;
    menuElement.style.position = "fixed";
    menuElement.style.margin = "0";
}
