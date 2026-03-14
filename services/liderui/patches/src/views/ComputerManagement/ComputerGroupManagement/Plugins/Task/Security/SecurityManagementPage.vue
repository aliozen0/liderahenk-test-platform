<template>
  <div>
    <div class="p-grid">
      <div class="p-col-12 p-md-6 p-lg-12">
        <network-management
          v-if="networkManagementState && isExistPrivilege('ROLE_NETWORK_MANAGER')"
          class="plugin-card"
          :pluginTask="pluginTaskNetworkManagement"
          :isGroup="true">
        </network-management>
      </div>
    </div>
  </div>
</template>

<script>
import NetworkManagement from "@/views/ComputerManagement/Plugins/Task/Security/NetworkManagement/NetworkManagement.vue";
import { taskService } from '../../../../../../services/Task/TaskService.js';
import { roleManagement } from "../../../../../../services/Roles/RoleManagement";

export default {
  data() {
    return {
      pluginTaskNetworkManagement: null,
      networkManagementState: false,
    };
  },

  components: {
    NetworkManagement,
  },

  created() {
    this.pluginTaskList();
  },

  methods: {
    isExistPrivilege(role){
      return roleManagement.isExistRole(role);
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
          if (element.page == "network-manager") {
            this.pluginTaskNetworkManagement = element;
            this.networkManagementState = element.state;
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
