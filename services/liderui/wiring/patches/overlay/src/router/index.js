import { createRouter, createWebHashHistory } from "vue-router";
import Dashboard from '@/views/Dashboard/Dashboard.vue';
import AuthLayout from '@/layouts/AuthLayout.vue';
import Login from '@/views/Login/Login.vue';
import ComputerManagementTab from '@/views/ComputerManagement/ComputerManagementTab.vue';
import FullLayout from '@/layouts/FullLayout.vue';

import AgentReport from '@/views/Reports/AgentReport/AgentReport.vue';
import TaskReport from '@/views/Reports/TaskReport.vue';
import LogReport from '@/views/Reports/SystemLogReport.vue';
import ScheduledTaskReport from '@/views/Reports/ScheduledTaskReport.vue';
import SessionReport from '@/views/Reports/SessionReport/SessionReport.vue';

import ServerSettings from '@/views/Settings/ServerSettings/ServerSettings.vue';
import SystemMonitoringDefinitions from '@/views/Settings/SystemMonitoringDefinitions/SystemMonitoringDefinitions.vue';
import ScriptDefinitions from '@/views/Settings/ScriptDefinitions/ScriptDefinitions.vue';
import RegistrationTemplates from '@/views/Settings/RegistrationTemplates/RegistrationTemplates.vue';
import ConsoleUserSettings from '@/views/Settings/ConsoleUserSettings/ConsoleUserSettings.vue';
import ServerInformations from '@/views/Settings/ServerInformations/ServerInformations.vue';

import UserManagementTab from '@/views/UserManagement/UserManagementTab.vue';
import UserProfile from '@/views/Profile/Profile.vue';
import PolicyManagement from '@/views/PolicyManagement/PolicyManagement.vue';
import RemoteAccessScreem from '@/views/ComputerManagement/Plugins/Task/RemoteAccess/RemoteAccessScreen.vue';
import ForgotPassword from '@/views/Login/ForgotPassword.vue';
import ResetPassword from '@/views/Login/ResetPassword.vue';

import { featureGate } from "@/platform/routes";
import { beforeEachAuthGuard } from "@/platform/guards";

const routes = [
    featureGate({
        path: '/remote-access',
        name: 'Remote Access',
        component: RemoteAccessScreem,
        meta: {
            requiresAuth: true,
            feature: 'remote-access',
            roles: ['ROLE_REMOTE_ACCESS'],
        },
    }, 'remote-access'),
    {
        path: "/",
        redirect: "/dashboard",
        component: FullLayout,
        name: "Dashboards",
        children: [
            {
                path: "/dashboard",
                name: "Dashboard",
                components: { default: Dashboard },
                meta: { requiresAuth: true },
            },
            {
                path: "/computer",
                name: "ComputerManagement",
                components: { default: ComputerManagementTab },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_COMPUTERS'],
                },
            },
            {
                path: "/user",
                name: "UserManagement",
                components: { default: UserManagementTab },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_USERS'],
                },
            },
            {
                path: "/reports/agent",
                name: "AgentReport",
                components: { default: AgentReport },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_AGENT_INFO'],
                },
            },
            {
                path: "/reports/task",
                name: "TaskReport",
                components: { default: TaskReport },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_EXECUTED_TASK'],
                },
            },
            {
                path: "/reports/logs",
                name: "LogReport",
                components: { default: LogReport },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_OPERATION_LOG'],
                },
            },
            {
                path: "/reports/scheduled",
                name: "ScheduledReport",
                components: { default: ScheduledTaskReport },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_SCHEDULE_TASK_REPORT'],
                },
            },
            {
                path: "/reports/session",
                name: "SessionReport",
                components: { default: SessionReport },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_USER_SESSION_REPORT'],
                },
            },
            {
                path: '/settings/server-settings',
                name: 'ServerSettings',
                components: { default: ServerSettings },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_SERVER_SETTINGS'],
                },
            },
            featureGate({
                path: '/settings/system-monitoring-definitions',
                name: 'SystemMonitoringDefinitions',
                components: { default: SystemMonitoringDefinitions },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_CONKY_DEFINITION'],
                    feature: 'conky',
                },
            }, 'conky'),
            {
                path: '/settings/script-definitions',
                name: 'ScriptDefinitions',
                components: { default: ScriptDefinitions },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_SCRIPT_DEFINITION'],
                },
            },
            {
                path: '/settings/registration-templates',
                name: 'RegistrationTemplates',
                components: { default: RegistrationTemplates },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_REGISTRATION_TEMPLATE'],
                },
            },
            {
                path: '/settings/console-user-settings',
                name: 'ConsoleUserSettings',
                components: { default: ConsoleUserSettings },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_CONSOLE_ACCESS_SETTINGS'],
                },
            },
            {
                path: '/settings/server-informations',
                name: 'ServerInformations',
                components: { default: ServerInformations },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_SERVER_INFORMATION'],
                },
            },
            {
                path: '/user-profile',
                name: 'User Profile',
                components: { default: UserProfile },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_USER'],
                },
            },
            {
                path: '/policy',
                name: 'Policy Management',
                components: { default: PolicyManagement },
                meta: {
                    requiresAuth: true,
                    roles: ['ROLE_POLICY'],
                },
            },
        ],
    },
    {
        path: "/",
        redirect: "/",
        component: AuthLayout,
        children: [
            {
                path: "/login",
                name: "Login",
                components: { default: Login },
                meta: { guest: true },
            },
            {
                path: "/forgot-password",
                name: "ForgotPassword",
                components: { default: ForgotPassword },
                meta: { guest: true },
            },
            {
                path: "/forgot-password/id/:uuid",
                name: "Reset Password",
                components: { default: ResetPassword },
                meta: { guest: true },
            },
        ],
    },
];

const router = createRouter({
    history: createWebHashHistory(),
    linkActiveClass: "active",
    routes,
});

router.beforeEach(beforeEachAuthGuard);

export default router;
