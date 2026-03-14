<template>
    <node-detail :showNodeDetailDialog="showNodeDetailDialog"
        :selectedNode="selectedNode"
        @close-node-detail-dialog="showNodeDetailDialog=false">
    </node-detail>
    <div class="p-grid computer-group-management">
        <div class="p-col-12 p-md-6 p-lg-3" style="min-height:90vh; background-color:#fff;padding-left:20px;margin-top:10px;">
            <tree-component 
                ref="tree"
                loadNodeUrl="/api/lider/computer-groups/groups"
                loadNodeOuUrl="/api/lider/computer-groups/ou-details"
                :treeNodeClick="treeNodeClick"
                :searchFields="searchFields"
                @handleContextMenu="handleContenxtMenu"
            >
                <template #contextmenu>
                    <div
                        ref="treecontextmenu"
                        class="el-overlay mycontextmenu"
                        v-show="showContextMenu"
                        @click="showContextMenu = false"
                        >
                        <div ref="rightMenu">
                            <Menu :model="contextMenuItems"/>
                        </div>
                    </div>
                </template>
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
                    >
                    </Button>
                    <Button
                        icon="fa fa-cubes"
                        :class="selectedPluginTab == 'package-management' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                        @click="setSelectedPluginTab('package-management')"
                        :label="$t('computer.plugins.button.package')"
                        v-if="isExistPrivilege([
                            'ROLE_PACKAGE_INSTALL_REMOVE',
                            'ROLE_PACKAGE_CONTROL'
                        ])"
                    >
                    </Button>
                    <Button
                        icon="fa fa-code"
                        :class="selectedPluginTab == 'script-management' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                        @click="setSelectedPluginTab('script-management')"
                        :label="$t('computer.plugins.button.script')"
                        v-if="isExistPrivilege([
                            'ROLE_SCRIPT',
                        ])"
                    >
                    </Button>
                    <Button
                        icon="fas fa-shield-alt"
                        :class="selectedPluginTab == 'security-management' ? 'p-button-raised p-button-sm p-mr-2 p-mb-2':'p-button-text p-button-sm p-mr-2 p-mb-2'"
                        @click="setSelectedPluginTab('security-management')"
                        :label="$t('computer.plugins.button.security')"
                        v-if="isExistPrivilege([
                            'ROLE_NETWORK_MANAGER',
                            'ROLE_DEVICE_MANAGEMENT',
                            'ROLE_USB_RULE'
                        ])"
                    >
                    </Button>
                </div>
                <div class="p-col">
                    <keep-alive>
                        <component :is="selectedPluginTab"></component>
                    </keep-alive>
                </div>
            </div>
        </div>
    </div>
    <!-- Add Folder Dialog -->
    <Dialog :header="$t('group_management.add_folder')" v-model:visible="modals.folderAdd" 
        :style="{width: '30vw'}" :modal="true">
        <div class="p-fluid">
            <div class="p-field">
                <label for="folderName">{{$t('group_management.folder_name')}}</label>
                <InputText :class="validation.folderName ? 'p-invalid': ''" type="text" v-model="folderName"/>
                <small v-if="validation.folderName" class="p-error">
                    {{ $t('group_management.folder_name_warn')}}
                </small>
            </div>
        </div>
        <template #footer>
            <Button :label="$t('group_management.cancel')" icon="pi pi-times" 
                @click="modals.folderAdd = false" class="p-button-text p-button-sm"
            />
            <Button :label="$t('group_management.add')" icon="pi pi-plus"
                @click="addFolder" class="p-button-sm"
            />
        </template>
    </Dialog>
    <!-- Add Folder Dialog End-->
    <!-- Rename Group Dialog -->
    <Dialog :header="$t('group_management.rename_group')" 
        v-model:visible="modals.renameGroup" :style="{width: '30vw'}" :modal="true">
        <div class="p-fluid">
            <div class="p-field">
                <label for="folderName">{{$t('group_management.group_name')}}</label>
                <InputText :class="validation.groupName ? 'p-invalid': ''" type="text" v-model="agentGroupModal.groupName"/>
                <small v-if="validation.groupName" class="p-error">
                    {{ $t('group_management.group_name_warn')}}
                </small>
            </div>
        </div>
        <template #footer>
            <Button :label="$t('group_management.cancel')" icon="pi pi-times" 
                @click="modals.renameGroup = false" class="p-button-text p-button-sm"
            />
            <Button :label="$t('group_management.update')" icon="pi pi-refresh"
                @click="changeGroupName" class="p-button-sm"
            />
        </template>
    </Dialog>
    <!-- Rename Group Dialog End -->
    <!-- Delete Selected Node Dialog -->
    <Dialog
        :header="$t('computer.task.toast_summary')" 
        v-model:visible="modals.deleteNode"  
        :modal="true" 
        @hide="modals.deleteNode = false">
        <div class="confirmation-content">
            <i class="pi pi-info-circle p-mr-3" style="font-size: 2rem" />
            <span v-if="selectedNode.type == 'GROUP'">
                {{ $t('group_management.delete_group_warn')}}
            </span>
            <span v-if="selectedNode.type == 'ORGANIZATIONAL_UNIT'">
                {{ $t('group_management.delete_folder_warn')}}
            </span>
        </div>
        <template #footer>
        <Button 
            :label="$t('user_management.cancel')" 
            icon="pi pi-times" 
            @click="modals.deleteNode = false" 
            class="p-button-text p-button-sm"
        />
        <Button 
            :label="$t('user_management.yes')"
            icon="pi pi-check" 
            @click="deleteNode"
            class="p-button-sm"
        />
        </template>
    </Dialog>
    <!-- Delete Selected Node Dialog End -->
    <!-- Move Selected Node Dialog -->
    <Dialog 
        :header="selectedNode && selectedNode.type=='GROUP'? $t('group_management.move_group')
        :$t('group_management.move_folder')" 
        v-model:visible="modals.moveNode" :style="{width: '40vw'}" :modal="true"
    >
        <tree-component 
            ref="movetree"
            :isMove="true"
            loadNodeUrl="/api/lider/computer-groups/groups"
            loadNodeOuUrl="/api/lider/computer-groups/ou-details"
            :treeNodeClick="moveTreeNodeClick"
            :searchFields="searchFolderFields"
            :scrollHeight="40"
        />
        <div class="p-col p-text-center">
          <small>{{$t('group_management.select_folder_warn')}}</small>
        </div>
        <template #footer>
            <Button :label="$t('group_management.cancel')" icon="pi pi-times" 
                @click="modals.moveNode = false" class="p-button-text p-button-sm"
            />
            <Button :label="$t('group_management.move')" icon="el-icon-rank" 
                @click="moveNode" class="p-button-sm"
            />
        </template>
    </Dialog>
    <!-- Move Selected Node Dialog End -->

    <!-- Add Group Dialog -->
    <Dialog 
        :header="selectedNode && selectedNode.type=='GROUP'? $t('group_management.add_group')
        :$t('group_management.add_group')" 
        v-model:visible="modals.addToGroup" :style="{width: '40vw'}" :modal="true"
    >  
        <tree-component 
                ref="tree"
                loadNodeUrl="/api/lider/computer-groups/groups"
                loadNodeOuUrl="/api/lider/computer-groups/ou-details"
                :treeNodeClick="treeNodeClick"
                :searchFields="searchFields"
                :showCheckbox="agentGroupModal.showCheckbox"
                :getCheckedNodes="getCheckedAgentNodes"
                @handleContextMenu="handleContenxtMenu"
            >
            </tree-component>
        <div class="p-col p-text-center">
          <small>{{$t('group_management.group_name_warn')}}</small>
        </div>
        <template #footer>
            <Button :label="$t('group_management.cancel')" icon="pi pi-times" 
                @click="modals.addToGroup = false" class="p-button-text p-button-sm"
            />
            <Button :label="$t('group_management.add')" icon="el-icon-rank" 
                @click="groupManagemenet" class="p-button-sm"
            />
        </template>
    </Dialog>
    <!-- Add Group Dialog End -->

    <!-- Add Group Dialog or Add Client to Group Dialog -->
    <Dialog :header="modals.addClient? $t('group_management.add_client')
        :$t('group_management.create_group')"
         v-model:visible="modals.addGroup" :style="{width: '50vw'}" :modal="true">
        <TabView>
            <TabPanel :header="$t('group_management.group_info')">
                <div class="p-fluid">
                    <div class="p-field">
                        <label for="agentGroupModal.groupName">{{$t('group_management.group_name')}}</label>
                        <InputText :class="validation.groupName ? 'p-invalid': ''" 
                            type="text" v-model="agentGroupModal.groupName"
                            :disabled="modals.addClient? true: false"/>
                        <small v-if="validation.groupName" class="p-error">
                            {{ $t('group_management.group_name_warn')}}
                        </small>
                    </div>
                </div>
                <tree-component 
                    ref="agenttree"
                    loadNodeUrl="/api/lider/computer/computers"
                    loadNodeOuUrl="/api/lider/computer/ou-details"
                    :showCheckbox="agentGroupModal.showCheckbox"
                    :getCheckedNodes="getCheckedAgentNodes"
                    :searchFields="searchAgentFields"
                    isAgentTree="true"
                    :scrollHeight="40"
                />
                <div class="p-col p-text-center">
                    <small>{{$t('group_management.select_client')}}</small>
                </div>
            </TabPanel>
            <!-- <TabPanel>
                <template #header>
                    <span>{{$t('group_management.selected_clients')}}
                        <Badge v-if="agentGroupModal.checkedNodes.length > 0" :value="agentGroupModal.checkedNodes.length"></Badge>
                    </span>
                </template>
                <DataTable :value="agentGroupModal.checkedNodes" v-model:filters="filters"
                    class="p-datatable-sm" style="margin-top: 2em" 
                    responsiveLayout="stack" :loading="loading"
                    :paginator="true" :rows="10"
                    paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown" 
                    :rowsPerPageOptions="[10,25,50]">
                    <template #header>
                        <div class="p-d-flex p-jc-end">
                            <span class="p-input-icon-left">
                                <i class="pi pi-search"/>
                                <InputText 
                                    v-model="filters['global'].value" 
                                    class="p-inputtext-sm" 
                                    :placeholder="$t('group_management.search')" 
                                />
                            </span>
                        </div>
                    </template>
                    <Column field="distinguishedName" 
                        :header="$t('group_management.node_dn')" 
                        style="min-width: 80%">
                    </Column>
                    <Column>
                        <template #body="slotProps">
                            <div class="p-d-flex p-jc-end">
                                <Button
                                    class="p-button-sm p-button-danger p-button-rounded"
                                    icon="pi pi-trash"
                                    :title="$t('group_management.delete')"
                                    @click.prevent="removeAgentFromGroup(slotProps.data)">
                                </Button>
                            </div>
                        </template>
                    </Column>
                </DataTable>
            </TabPanel> -->
            <TabPanel v-if="modals.addClient">
                <template #header>
                    <span>{{$t('group_management.existing_clients')}}
                         <Badge v-if="agentGroupModal.checkedNodes.length > 0" :value="agentGroupModal.existingClients.length"></Badge>
                    </span>
                </template>
                <DataTable :value="agentGroupModal.existingClients" v-model:filters="filters"
                    class="p-datatable-sm" style="margin-top: 2em" 
                    responsiveLayout="stack" :loading="loading"
                    :paginator="true" :rows="10"
                    paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown" 
                    :rowsPerPageOptions="[10,25,50]">
                    <template #header>
                        <div class="p-d-flex p-jc-end">
                            <span class="p-input-icon-left">
                                <i class="pi pi-search"/>
                                <InputText 
                                    v-model="filters['global'].value" 
                                    class="p-inputtext-sm" 
                                    :placeholder="$t('group_management.search')" 
                                />
                            </span>
                        </div>
                    </template>
                    <Column field="distinguishedName" 
                        :header="$t('group_management.node_dn')">
                    </Column>
                </DataTable>
            </TabPanel>
        </TabView>
        <div v-if="loadingGroup" class="p-text-center">
            <i style="font-size: 1.5rem" class="el el-icon-loading"></i>&nbsp;
            <a class="primary" v-if="modals.addClient">
                {{$t('group_management.add_client_loading')}}
            </a>
            <a class="primary" v-else>
                {{$t('group_management.add_group_loading')}}
            </a>
        </div>
        <template #footer>
            <Button :label="$t('user_management.cancel')" icon="pi pi-times" 
                @click="modals.addGroup = false" class="p-button-text p-button-sm"
            />
            <Button :label="$t('user_management.add')" icon="pi pi-user-plus" 
                @click="groupManagemenet" class="p-button-sm"
            />
        </template>
    </Dialog>
    <!-- Add Group Dialog or Add Client to Group Dialog End -->
</template>

<script>

/**
 * Computer Group Management.
 * @see {@link http://www.liderahenk.org.tr/}
 * 
 */

import TreeComponent from '@/components/Tree/TreeComponent.vue';
import NodeDetail from '@/components/Tree/NodeDetail.vue';
import SystemManagement from "@/views/ComputerManagement/ComputerGroupManagement/Plugins/Task/System/SystemManagementPage.vue";
import PackageManagement from "@/views/ComputerManagement/ComputerGroupManagement/Plugins/Task/Package/PackageManagementPage.vue";
import ScriptManagement from "@/views/ComputerManagement/ComputerGroupManagement/Plugins/Task/Script/ScriptManagementPage.vue";
import SecurityManagement from "@/views/ComputerManagement/ComputerGroupManagement/Plugins/Task/Security/SecurityManagementPage.vue";
import { mapActions } from "vuex"
import {ref} from 'vue';
import {FilterMatchMode} from 'primevue/api';
import { computerGroupsManagementService } from '../../../services/ComputerManagement/ComputerGroupManagement.js';
import { roleManagement } from "../../../services/Roles/RoleManagement.js"

export default {
    setup(){
        const selectedNode = ref(null);
        const tree = ref(null);
        return { selectedNode, tree };
    },

    components: {
        TreeComponent,
        NodeDetail,
        SystemManagement,
        PackageManagement,
        ScriptManagement,
        SecurityManagement
    },

    data() {
        return {
            selectedPluginTab: "system-management",
            showNodeDetailDialog: false,
            moveFolderNode: null,
            // addGroupNode : null,
            showContextMenu: false,
            loading: false,
            loadingGroup: false,
            modals : {
                folderAdd: false,
                renameGroup: false,
                moveFolder: false,
                addClient: false,
                addGroup: false,
                deleteNode: false,
                moveNode: false,
                addToGroup: false
            },
            folderName:'',
            selectedAgents: [],
            validation: {
                folderName: false,
                groupName: false
            },
            agentGroupModal: {
                showCheckbox: true,
                groupName:'',
                checkedNodes: [],
                existingClients: []
            },
            searchFields: [
                {
                    key: this.$t('tree.name'),
                    value: "cn"
                },
                {
                    key: this.$t('tree.folder'),
                    value: "ou"
                },
            ],
            searchAgentFields: [
                {
                    key: this.$t('tree.cn'),
                    value: "cn"
                },
                {
                    key: this.$t('tree.uid'),
                    value: "uid"
                },
                {
                    key: this.$t('tree.folder'),
                    value: "ou"
                },
            ],
            searchFolderFields: [
                {
                    key: this.$t('tree.folder'),
                    value: "ou"
                },
            ],
            filters: {
                'global': {value: null, matchMode: FilterMatchMode.CONTAINS}
            }
        }
    },

    created() {
        this.setSelectedComputerGroupNode(null);
    },

    methods: {
        ...mapActions(["setSelectedComputerGroupNode"]),

        isExistPrivilege(roles) {
            return roleManagement.hasAnyRole(roles)
        },  

        
        treeNodeClick(node) {
            this.selectedNode = node;
            this.setSelectedComputerGroupNode(node);
        },

        handleContenxtMenu(data, node, treenode, tree){
            data.preventDefault();
            this.treeNodeClick(node);
            switch(node.type) {
                case 'ORGANIZATIONAL_UNIT':
                    if (node.isRoot) {
                        this.contextMenuItems = [
                            {
                                label: this.$t('group_management.node_detail'), 
                                icon:'pi pi-list', 
                                command: () => {this.showNodeDetailDialog = true}
                            },
                            {
                                label: this.$t('group_management.create_group'), 
                                icon:"fas fa-users", 
                                command: () => {this.modals.addClient = false; 
                                    this.modals.addGroup = true;
                                    this.agentGroupModal.groupName = '';}
                            },
                            {
                                label: this.$t('group_management.add_folder'),
                                icon:"pi pi-folder-open", 
                                command: () => {this.validation.folderName = false; this.modals.folderAdd = true}
                            },
                        ]
                    } else {
                        this.contextMenuItems = [
                            {
                                label: this.$t('group_management.node_detail'), 
                                icon: 'pi pi-list', 
                                command: () => {this.showNodeDetailDialog = true}
                            },
                            {
                                label: this.$t('group_management.add_group'), 
                                icon:"fas fa-users", 
                                command: () => {this.modals.addClient = false; 
                                    this.modals.addGroup = true;
                                    this.agentGroupModal.groupName = '';}
                            },
                            {
                                label: this.$t('group_management.add_folder'), 
                                icon:"pi pi-folder-open", 
                                command: () => {this.validation.folderName = false; 
                                    this.modals.folderAdd = true;
                                    this.folderName = '';}
                            },
                            {
                                label: this.$t('group_management.move_folder'), 
                                icon:"el-icon-rank", 
                                command:() => {this.modals.moveNode = true;}
                            },
                            {
                                label: this.$t('group_management.delete_folder'), 
                                icon:"pi pi-trash", 
                                command:() => {this.modals.deleteNode = true;}
                            },
                        ]
                    }
                    break
                case 'GROUP':
                    this.contextMenuItems = [
                        {
                            label: this.$t('group_management.node_detail'), 
                            icon: 'pi pi-list', 
                            command: () => {this.showNodeDetailDialog = true}
                        },
                        {
                            label: this.$t('group_management.add_client'), 
                            icon:"fab fa-linux", 
                            command: () => {this.showAddClientDialog()}
                        },
                        {
                            label: this.$t('group_management.rename_group'), 
                            icon:"pi pi-pencil", 
                            command: () => {this.modals.renameGroup = true; 
                                this.validation.groupName = false;
                                this.agentGroupModal.groupName = this.selectedNode.cn}
                        },
                        {
                            label: this.$t('group_management.move_group'), 
                            icon:"el-icon-rank", 
                            command: () => {this.modals.moveNode = true}
                        },
                        {
                            label: this.$t('group_management.delete_group'), 
                            icon:"pi pi-trash", 
                            command:() => {this.modals.deleteNode = true;}
                        },
                        {
                            label: this.$t('group_management.add_group'), 
                            icon:"fas fa-users", 
                            command: () => {this.showAddGroupDialog()}
                        },
                    ]
            }
            this.$refs.rightMenu.style.top = data.clientY + 'px';
            this.$refs.rightMenu.style.left = data.clientX + 'px';
            this.$refs.rightMenu.style.position = 'fixed';
            this.$refs.rightMenu.style.margin = '0';
            this.$refs.rightMenu.style.backgroundColor = '0';
            this.showContextMenu = !this.showContextMenu;
        },

        moveTreeNodeClick(node) {
            //*** This method for tree that is created for folder move dialog.  */
            this.moveFolderNode = node;
        },

        // addTreeNodeClick(node) {
        //     this.addGroupNode = node;
        // },

        async addFolder() {
            if (!this.folderName.trim()) {
                this.validation.folderName = true;
                return;
            }
            const{response,error} = await computerGroupsManagementService.addOu({
                parentName: this.selectedNode.distinguishedName,
                type:'ORGANIZATIONAL_UNIT',
                ou: this.folderName,
                distinguishedName: 'ou=' + this.folderName + ',' + this.selectedNode.distinguishedName,
                name: this.folderName
            })
            if(response.status == 200){
                this.$refs.tree.append(response.data, this.selectedNode);
                this.modals.folderAdd = false;
                this.$toast.add({
                    severity:'success', 
                    detail: this.$t('group_management.add_folder_success'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
            }
            else{
                this.$toast.add({
                    severity:'error', 
                    detail: this.$t('group_management.error_add_folder'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
            }
    
            this.folderName = '';
            this.modals.folderAdd = false;
        },

        async changeGroupName() {
            if (!this.agentGroupModal.groupName.trim()) {
                this.validation.groupName = true;
                return;
            }
            this.modals.renameGroup = false;
            let params = new FormData();
            params.append("oldDN", this.selectedNode.distinguishedName);
            params.append("newName", "cn="+this.agentGroupModal.groupName);
            const{response,error} = await computerGroupsManagementService.renameEntry(params);
            if(error){
                this.$toast.add({
                    severity:'error', 
                    detail: this.$t('group_management.rename_group_error'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
            }
            else{
                if(response.status == 200) {
                    if (response.data) {
                        this.$toast.add({
                            severity:'success', 
                            detail: this.$t('group_management.rename_group_success'), 
                            summary:this.$t("computer.task.toast_summary"), 
                            life: 3000
                            });
                        this.selectedNode.distinguishedName = response.data.distinguishedName;
                        this.selectedNode.name = response.data.name;
                        this.$refs.tree.updateNode(this.selectedNode.distinguishedName, this.selectedNode);
                        this.setSelectedComputerGroupNode(response.data);
                    }
                }
                else if(response.status == 417){
                    this.$toast.add({
                        severity:'error', 
                        detail: this.$t('group_management.error_417_rename_group_name'), 
                        summary:this.$t("computer.task.toast_summary"), 
                        life: 3000
                    });
                }
            }
        },

        async moveNode() {
            if (!this.moveFolderNode) {
                this.$toast.add({
                    severity:'warn', 
                    detail: this.$t('group_management.select_folder_warn'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
                return;
            }
            if (this.moveFolderNode.distinguishedName === this.selectedNode.distinguishedName) {
                this.$toast.add({
                    severity:'warn', 
                    detail: this.$t('group_management.move_node_same_dn_warn'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
                return;
            }
            let params = new FormData();
            params.append("sourceDN", this.selectedNode.distinguishedName);
            params.append("destinationDN", this.moveFolderNode.distinguishedName);
            this.modals.moveNode = false;
            const{ response,error } = await computerGroupsManagementService.moveEntry(params);
            if(error){
                this.$toast.add({
                    severity:'error', 
                    detail: this.$t('group_management.move_node_error'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
            }
            else{
                if(response.status == 200){
                    if (response.data) {
                        this.$refs.tree.remove(this.selectedNode);
                        if (this.selectedNode.type === "GROUP") {
                            this.selectedNode.distinguishedName = "cn="+ this.selectedNode.cn + ","+ this.moveFolderNode.distinguishedName;
                        } else {
                            this.selectedNode.distinguishedName = "ou="+ this.selectedNode.ou + ","+ this.moveFolderNode.distinguishedName;
                        }
                        this.$refs.tree.append(this.selectedNode, this.$refs.tree.getNode(this.moveFolderNode.distinguishedName));
                        this.setSelectedComputerGroupNode(null);
                        this.$toast.add({
                            severity:'success', 
                            detail: this.$t('group_management.move_node_success'), 
                            summary:this.$t("computer.task.toast_summary"), 
                            life: 3000
                        });
                    }

                }
                else if(response.status == 417){
                    this.$toast.add({
                        severity:'error', 
                        detail: this.$t('group_management.error_417_move_entry'), 
                        summary:this.$t("computer.task.toast_summary"), 
                        life: 3000
                    });
                }


            }
        },

        async groupManagemenet() {
            if (this.agentGroupModal.checkedNodes.length === 0) {
                this.$toast.add({
                    severity:'warn', 
                    detail: this.$t('group_management.select_client'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
                return;
            }
            if (this.modals.addClient || this.modals.addToGroup) {
                this.addClientToGroup();
            } else {
                this.createAgentGroup();
            }
        },

        async createAgentGroup() {
            if (!this.agentGroupModal.groupName.trim()) {
                this.validation.groupName = true;
                return;
            }
            this.loading = true;
            this.loadingGroup = true;
            const{response,error} = await computerGroupsManagementService.createNewGroup({
                groupName: this.agentGroupModal.groupName,
                checkedEntries: JSON.stringify(this.agentGroupModal.checkedNodes),
                selectedOUDN: this.selectedNode.distinguishedName
            })
            if(error){
                if (error.response.status == "NOT_ACCEPTABLE") {
                    this.$toast.add({
                        severity:'error', 
                        detail: this.$t('group_management.select_client'),
                        summary:this.$t("computer.task.toast_summary"), 
                        life: 5000
                    });
                } 
            }
            else{
                if(response.status == 200){
                    this.loading = false;
                    this.loadingGroup = false;
                    if (response.data === "") {
                        this.$toast.add({
                            severity:'error', 
                            detail: this.$t('group_management.created_group_error'), 
                            summary:this.$t("computer.task.toast_summary"), 
                            life: 3000
                        });
                    } else {
                        this.$refs.tree.append(response.data, this.selectedNode);
                        this.agentGroupModal = {
                            showCheckbox: true,
                            groupName:'',
                            checkedNodes: []
                        }
                        this.modals.addGroup = false;
                        this.$toast.add({
                            severity:'success', 
                            detail: this.$t('group_management.created_group_success'), 
                            summary:this.$t("computer.task.toast_summary"), 
                            life: 3000
                        });
                    }
                }
                else if(response.status == 417){
                    this.$toast.add({
                        severity:'error', 
                        detail: this.$t('group_management.error_417_created_group'), 
                        summary:this.$t("computer.task.toast_summary"), 
                        life: 3000
                    });
                }
            }

        },

        showAddClientDialog() {
            this.agentGroupModal.groupName = this.selectedNode.cn;
            this.modals.addGroup = true;
            this.modals.addClient = true;
            this.getMemberOfSelectedGroup();
        },

        showAddGroupDialog() {
            this.agentGroupModal.groupName = this.selectedNode.cn;
            // this.modals.addGroup = true;
            // this.modals.addClient = true;
            this.modals.addToGroup = true;
            this.getMemberOfSelectedGroup();
        },

        async addClientToGroup() {
            this.loadingGroup = true;
            const{response,error} = await computerGroupsManagementService.groupExisting(
                {checkedEntries: JSON.stringify(this.agentGroupModal.checkedNodes),
                groupDN: this.selectedNode.distinguishedName});

            if(error){
                this.$toast.add({
                    severity:'error', 
                    detail: this.$t('group_management.add_client_error'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
            }
            else{
                this.loading = false;
                this.loadingGroup = false;
                if(response.status == 200){
                    if (response.data) {
                        this.selectedNode.attributesMultiValues = response.data.attributesMultiValues;
                        this.setSelectedComputerGroupNode(response.data);
                        this.agentGroupModal = {
                            showCheckbox: true,
                            groupName:'',
                            checkedNodes: [],
                            existingClients: []
                        }
                        this.modals.addGroup = false;
                        this.modals.addClient = false;
                        this.modals.addToGroup = false;
                        this.$toast.add({
                            severity:'success', 
                            detail: this.$t('group_management.add_client_success'), 
                            summary:this.$t("computer.task.toast_summary"), 
                            life: 3000
                        });
                    }
                }
                else if(response.status == 417){
                    this.$toast.add({
                        severity:'error', 
                        detail: this.$t('group_management.error_417_add_client'), 
                        summary:this.$t("computer.task.toast_summary"), 
                        life: 3000
                    });
                }
            }
        },

        getMemberOfSelectedGroup() {
            for (var key in this.selectedNode.attributesMultiValues) {
				if (this.selectedNode.attributesMultiValues.hasOwnProperty(key) && key == "member") {
					if(this.selectedNode.attributesMultiValues[key].length > 1) {
                        this.attributesMultiValue = true;
                        console.log(this.selectedNode.attributesMultiValues)
						for(var i = 0; i< this.selectedNode.attributesMultiValues[key].length; i++) {
                            this.agentGroupModal.existingClients.push({
                                "distinguishedName": this.selectedNode.attributesMultiValues[key][i],
                            });
                        }
                    } else {
                        this.attributesMultiValue = false;
                        this.agentGroupModal.existingClients.push({
                            "distinguishedName": this.selectedNode.attributesMultiValues[key][0],
                        });
                    }
                }
            }
        },

        async deleteNode() {
            let params = new FormData();
            params.append("dn", this.selectedNode.distinguishedName);
            this.modals.deleteNode = false;
            const{response,error} = await computerGroupsManagementService.deleteEntry(this.selectedNode.distinguishedName);
            if(error){
                this.$toast.add({
                    severity:'error', 
                    detail: this.$t('group_management.delete_node_error'), 
                    summary:this.$t("computer.task.toast_summary"), 
                    life: 3000
                });
            }
            else{
                if(response.status == 200){
                    if (response.data) {
                        this.$refs.tree.remove(this.selectedNode);
                        this.setSelectedComputerGroupNode(null);
                        this.$toast.add({
                            severity:'success', 
                            detail: this.$t('group_management.delete_node_success'), 
                            summary:this.$t("computer.task.toast_summary"), 
                            life: 3000
                        });
                    }
                }
                else if(response.status == 417){                    
                    this.$toast.add({
                        severity:'error', 
                        detail: this.$t('group_management.error_417_delete_node'), 
                        summary:this.$t("computer.task.toast_summary"), 
                        life: 3000
                    });
                }
            }
        },

        getCheckedAgentNodes(nodes) {
            this.agentGroupModal.checkedNodes = nodes;
            if (nodes.length === 0) {
                this.agentGroupModal.checkedNodes = [];
            }
        },

        removeAgentFromGroup(node) {
            this.agentGroupModal.checkedNodes = this.agentGroupModal.checkedNodes.filter(
                agent => {
                    if (agent.distinguishedName != node.distinguishedName) {
                        return agent;
                    } else {
                         this.$refs.tree.setCheckedNode(node.distinguishedName, false);
                    }
                }
            )
        }, 

        setSelectedPluginTab(tab) {
            this.selectedPluginTab = tab;
        },
    }, 

    watch: {
        selectedComputerGroupNode() {
            if (this.selectedNode && this.selectedNode.type == "GROUP") {
                this.selectedNode.attributesMultiValues.member = this.selectedComputerGroupNode.attributesMultiValues.member;
                this.$refs.tree.updateNode(this.selectedNode.distinguishedName, this.selectedNode);
            }
            
        }
    },
}
</script>

<style lang="scss" scoped>

.p-button:hover {
    box-shadow: 0 8px 16px 0 rgba(0,0,0,0.2);
}

.computer-group-management {
    background-color: #e7f2f8;
}

.mycontextmenu {
    background-color: rgba(0,0,0,0.0);
}

::v-deep(.p-paginator) {
    .p-paginator-current {
        margin-left: auto;
    }
}

::v-deep(.p-datatable.p-datatable-customers) {
    .p-paginator {
        padding: 1rem;
    }
}
</style>
