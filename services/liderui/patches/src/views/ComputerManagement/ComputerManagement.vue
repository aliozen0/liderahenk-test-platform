<template>
  <div class="p-grid computer-management">
      <div class="p-col-12 p-md-6 p-lg-3" style="min-height:90vh; background-color:#fff;padding-left:20px;margin-top:10px;">
          <div class="p-col">
            <div class="p-grid">
                <div class="p-col-12 p-md-6 p-lg-4">
                    <label><i class="pi pi-desktop" style="font-size: 0.8rem;"></i> {{$t('computer.total')}}:</label>
                    <a style="color: rgb(32, 99, 155); font-weight: bold;">&nbsp;{{agent.total == 0 ? '0': agent.total}}</a>
                </div>
                <div class="p-col-12 p-md-6 p-lg-4">
                    <label><i class="pi pi-desktop" style="font-size: 0.8rem;"></i> {{$t('computer.online')}}:</label>
                    <a style="color: #66BB6A; font-weight: bold;">&nbsp;{{agent.online == 0 ? '0': agent.online}}</a>
                </div>
                <div class="p-col-12 p-md-6 p-lg-4">
                    <label><i class="pi pi-desktop" style="font-size: 0.8rem;"></i> {{$t('computer.offline')}}:</label>
                    <a style="color: #D32F2F; font-weight: bold;">&nbsp;{{agent.offline == 0 ? '0': agent.offline}}</a>
                </div>
            </div>
        </div>
        <tree-component ref="tree"
            loadNodeUrl="/api/lider/computer/computers"
            loadNodeOuUrl="/api/lider/computer/ou-details"
            :treeNodeClick="treeNodeClick"
            isAgentTree="true"
            :searchFields="searchFields">
        </tree-component>
      </div>
      <div class="p-col-12 p-md-6 p-lg-9" style="margin-top:3px;">
          <div class="p-grid p-flex-column">
            <div class="p-col">
                <Button
                    icon="fa fa-sliders-h"
                    :class="selectedPluginTab == 'system-management' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                    @click="setSelectedPluginTab('system-management')"
                    :label="$t('computer.plugins.button.system')"
                />
                <Button
                    icon="fa fa-cubes"
                    :class="selectedPluginTab == 'package-management' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                    @click="setSelectedPluginTab('package-management')"
                    :label="$t('computer.plugins.button.package')"
                    v-if="isExistPrivilege([
                        'ROLE_PACKAGE_REPO',
                        'ROLE_PACKAGE_LIST',
                        'ROLE_PACKAGE_INSTALL_REMOVE',
                        'ROLE_PACKAGE_CONTROL'
                    ])"
                />
                <Button
                    icon="fa fa-code"
                    :class="selectedPluginTab == 'script-management' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                    @click="setSelectedPluginTab('script-management')"
                    :label="$t('computer.plugins.button.script')"
                    v-if="isExistPrivilege(['ROLE_SCRIPT'])"
                />
                <Button
                    icon="fas fa-shield-alt"
                    :class="selectedPluginTab == 'security-management' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                    @click="setSelectedPluginTab('security-management')"
                    :label="$t('computer.plugins.button.security')"
                    v-if="isExistPrivilege(['ROLE_NETWORK_MANAGER'])"
                />
                <Button
                    icon="fa fa-history"
                    :class="selectedPluginTab == 'task-history' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                    @click="setSelectedPluginTab('task-history')"
                    :label="$t('computer.plugins.button.history')"
                    v-if="isExistPrivilege(['ROLE_TASK_HISTORY'])"
                />
            </div>
            <div class="p-col">
                <keep-alive>
                    <component 
                        @move-selected-agent="moveSelectedAgent"
                        @delete-selected-agent="deleteSelectedAgent"
                        @rename-selected-agent="renameSelectedAgent"
                        @add-folder="addFolder"
                        :is="selectedPluginTab"
                    />
                </keep-alive>
            </div>
        </div>
    </div>
  </div>
</template>

<script>
import TreeComponent from '@/components/Tree/TreeComponent.vue';
import SystemManagement from "@/views/ComputerManagement/Plugins/Task/System/SystemManagementPage.vue";
import PackageManagement from "@/views/ComputerManagement/Plugins/Task/Package/PackageManagementPage.vue";
import ScriptManagement from "@/views/ComputerManagement/Plugins/Task/Script/ScriptManagementPage.vue";
import SecurityManagement from '@/views/ComputerManagement/Plugins/Task/Security/SecurityManagementPage.vue';
import TaskHistory from '@/views/ComputerManagement/Plugins/Task/TaskHistory/TaskHistory.vue';
import Dashboardbox from "@/components/Dashboardbox/Dashboardbox.vue";
import { mapActions, mapGetters } from "vuex";
import { computerManagementService } from '../../services/ComputerManagement/ComputerManagement.js';
import { roleManagement } from "../../services/Roles/RoleManagement.js";

export default {
    components: {
        TreeComponent,
        SystemManagement,
        PackageManagement,
        ScriptManagement,
        SecurityManagement,
        TaskHistory,
        Dashboardbox,
    },
    data() {
        return {
            selectedPluginTab: "system-management",
            searchFields: [
                { key: this.$t('tree.cn'), value: "cn" },
                { key: this.$t('tree.uid'), value: "uid" },
                { key: this.$t('tree.folder'), value: "ou" },
                { key: this.$t('tree.last_session'), value: "o" },
            ],
            agent: {
                total: 0,
                online: 0,
                offline: 0,
            },
        };
    },

    computed: {
        ...mapGetters(["selectedLiderNode"]),
    },

    created() {
        this.setSelectedLiderNode(null);
    },

    mounted() {
        this.getAgentonlineOfflineCount(null);
    },

    methods: {
        ...mapActions(["setSelectedLiderNode"]),

        isExistPrivilege(roles) {
            return roleManagement.hasAnyRole(roles);
        },

        setSelectedPluginTab(tab) {
            this.selectedPluginTab = tab;
        },

        treeNodeClick(node) {
            this.setSelectedLiderNode(node);
            this.getAgentonlineOfflineCount(node);
        },

        async getAgentonlineOfflineCount(node) {
            await this.getAgentCountList(node);
        },

        async getAgentCountList(node) {
            let params = new FormData();
            if (node) {
                if (node.type == "ORGANIZATIONAL_UNIT") {
                    params.append("searchDn", node.distinguishedName);
                    const { response, error } = await computerManagementService.computerAgentListSize(params);
                    if (error) {
                        this.$toast.add({
                            severity:'error',
                            detail: this.$t('computer.agent_info.error_agent_list_size'),
                            summary:this.$t("computer.task.toast_summary"),
                            life: 3000,
                        });
                    } else if (response.status == 200) {
                        this.agent.total = response.data.agentListSize;
                        this.agent.online = response.data.onlineAgentListSize;
                        this.agent.offline = this.agent.total - this.agent.online;
                    } else if (response.status == 417) {
                        this.$toast.add({
                            severity:'error',
                            detail: this.$t('computer.agent_info.error_417_agent_list_size'),
                            summary:this.$t("computer.task.toast_summary"),
                            life: 3000,
                        });
                    }
                } else if (node.type == "AHENK") {
                    this.agent.total = 1;
                    this.agent.online = node.online ? 1 : 0;
                    this.agent.offline = this.agent.total - this.agent.online;
                }
            } else {
                params.append("searchDn", "agents");
                const { response, error } = await computerManagementService.computerAgentListSize(params);
                if (error) {
                    this.$toast.add({
                        severity:'error',
                        detail: this.$t('computer.agent_info.error_agent_list_size'),
                        summary:this.$t("computer.task.toast_summary"),
                        life: 3000,
                    });
                } else if (response.status == 200) {
                    this.agent.total = response.data.agentListSize;
                    this.agent.online = response.data.onlineAgentListSize;
                    this.agent.offline = this.agent.total - this.agent.online;
                } else if (response.status == 417) {
                    this.$toast.add({
                        severity:'error',
                        detail: this.$t('computer.agent_info.error_417_agent_list_size'),
                        summary:this.$t("computer.task.toast_summary"),
                        life: 3000,
                    });
                }
            }
        },

        moveSelectedAgent(deletedNode, selectedNode, destinationDn) {
            this.$refs.tree.remove(deletedNode);
            this.$refs.tree.append(selectedNode, this.$refs.tree.getNode(destinationDn));
            this.setSelectedLiderNode(null);
        },

        deleteSelectedAgent(selectedNode) {
            this.$refs.tree.remove(selectedNode);
            this.setSelectedLiderNode(null);
        },

        renameSelectedAgent(selectedNode) {
            this.$refs.tree.updateNode(selectedNode.distinguishedName, this.selectedNode);
        },

        addFolder(folder, destinationDn){
            this.$refs.tree.append(folder, this.$refs.tree.getNode(destinationDn));
        },
    },
};
</script>

<style lang="scss" scoped>
.p-button:hover {
  box-shadow: 0 8px 16px 0 rgba(0,0,0,0.2);
}

.computer-management {
    background-color: #e7f2f8;
}
</style>
