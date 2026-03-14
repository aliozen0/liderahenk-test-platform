<template>
  <div>
    <div class="p-grid">
      <div class="p-col-12 p-md-6 p-lg-5">
        <agent-info class="plugin-card"
          :pluginTask="pluginTaskAgentInfo"
          @move-selected-agent="moveSelectedAgent"
          @delete-selected-agent="deleteSelectedAgent"
          @rename-selected-agent="renameSelectedAgent"
          @add-folder="addFolder">
        </agent-info>
        <local-user v-if="localUserState && isExistPrivilege('ROLE_LOCAL_USER')" class="plugin-card" :pluginTask="pluginTaskLocalUser"></local-user>
      </div>
      <div class="p-col-12 p-md-6 p-lg-7">
        <resource-usage v-if="resourceUsageState && isExistPrivilege('ROLE_RESOURCE_USAGE')" class="plugin-card" :pluginTask="pluginTaskResourceUsage"></resource-usage>
        <file-management v-if="fileManagementState && isExistPrivilege('ROLE_FILE_MANAGEMENT')" class="plugin-card" :pluginTask="pluginTaskFileManagement"></file-management>
      </div>
    </div>
  </div>
</template>

<script>
import AgentInfo from "@/views/ComputerManagement/Plugins/Task/System/AgentInfo.vue";
import ResourceUsage from "@/views/ComputerManagement/Plugins/Task/System/ResourceUsage.vue";
import LocalUser from "@/views/ComputerManagement/Plugins/Task/System/LocalUser.vue";
import FileManagement from "@/views/ComputerManagement/Plugins/Task/System/FileManagement.vue";
import { taskService } from '../../../../../services/Task/TaskService.js';
import { roleManagement } from "../../../../../services/Roles/RoleManagement";

export default {
  data() {
    return {
      pluginTaskResourceUsage: null,
      pluginTaskFileManagement: null,
      pluginTaskLocalUser: null,
      pluginTaskAgentInfo: null,
      resourceUsageState: false,
      fileManagementState: false,
      localUserState: false,
    };
  },
  components: {
    AgentInfo,
    ResourceUsage,
    LocalUser,
    FileManagement,
  },

  created() {
    this.pluginTaskList();
  },

  methods: {
    isExistPrivilege(role){
      return roleManagement.isExistRole(role);
    },

    moveSelectedAgent(deletedNode, selectedNode, destinationDn) {
      this.$emit('moveSelectedAgent', deletedNode, selectedNode, destinationDn);
    },

    deleteSelectedAgent(selectedNode) {
      this.$emit('deleteSelectedAgent', selectedNode);
    },

    renameSelectedAgent(selectedNode) {
      this.$emit('renameSelectedAgent', selectedNode);
    },

    addFolder(folder, destinationDn) {
      this.$emit('addFolder', folder, destinationDn);
    },

    async pluginTaskList() {
      const { response, error } = await taskService.pluginTaskList();
      if (error) {
        this.$toast.add({
          severity:'error',
          detail: this.$t('computer.plugins.security.error_plugin_task_list'),
          summary:this.$t("computer.task.toast_summary"),
          life: 3000,
        });
        return;
      }

      if (response.status == 200) {
        for (let index = 0; index < response.data.length; index++) {
          const element = response.data[index];
          if (element.page == "resource-usage") {
            this.pluginTaskResourceUsage = element;
            this.resourceUsageState = element.state;
          }
          if (element.page == "file-management") {
            this.pluginTaskFileManagement = element;
            this.fileManagementState = element.state;
          }
          if (element.page == "local-user") {
            this.pluginTaskLocalUser = element;
            this.localUserState = element.state;
          }
          if (element.page == "move-agent") {
            this.pluginTaskAgentInfo = element;
          }
        }
      } else if (response.status == 417) {
        this.$toast.add({
          severity:'error',
          detail: this.$t('computer.plugins.security.error_417_plugin_task_list'),
          summary:this.$t("computer.task.toast_summary"),
          life: 3000,
        });
      }
    },
  },
};
</script>

<style scoped>
.plugin-card{
  box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2);
  margin-bottom: 10px;
}
.plugin-card:hover {
  box-shadow: 0 8px 20px 0 rgba(155, 150, 150, 0.2);
}
</style>
