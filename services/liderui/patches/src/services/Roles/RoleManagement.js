import store from "../../store/store";
import { isFeatureEnabled, isRoleEnabled } from "../FeatureFlags";

class RoleManagement {
    getUserRole() {
        try {
            return store.getters.getUser?.priviliges || [];
        } catch {
            return [];
        }
    }

    isExistRole(isRole, allowAdminOverride = true) {
        const roles = this.getUserRole();
        if (!isRoleEnabled(isRole)) {
            return false;
        }
        if (allowAdminOverride && roles.includes("ROLE_ADMIN")) {
            return true;
        }
        return roles.includes(isRole);
    }

    hasAnyRole(requiredRoles = [], allowAdminOverride = true) {
        if (!requiredRoles || requiredRoles.length === 0) {
            return true;
        }

        const enabledRoles = requiredRoles.filter((role) => isRoleEnabled(role));
        if (enabledRoles.length === 0) {
            return false;
        }

        const roles = this.getUserRole();
        if (allowAdminOverride && roles.includes("ROLE_ADMIN")) {
            return true;
        }
        return enabledRoles.some((role) => roles.includes(role));
    }

    isFeatureEnabled(feature) {
        return isFeatureEnabled(feature);
    }
}

export const roleManagement = new RoleManagement();
