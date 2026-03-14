<template>
  <div>
    <div class="p-grid">
      <div class="p-col-12 p-md-6 p-lg-12">
        <member-of-agent-group class="plugin-card"></member-of-agent-group>
      </div>
    </div>
  </div>
</template>

<script>
import MemberOfAgentGroup from "@/views/ComputerManagement/ComputerGroupManagement/Plugins/Task/System/MemberOfAgentGroup.vue";

export default {
  components: {
    MemberOfAgentGroup,
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
