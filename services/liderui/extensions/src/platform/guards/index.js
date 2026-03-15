import { isFeatureEnabled } from "@/platform/feature-registry";
import { roleManagement } from "@/platform/guards/roleManagement";

export function beforeEachAuthGuard(to, from, next) {
    const hasDisabledFeature = to.matched.some(
        (record) => record.meta.feature && !isFeatureEnabled(record.meta.feature)
    );

    if (hasDisabledFeature) {
        return next({ path: "/dashboard", replace: true });
    }

    if (to.matched.some((record) => record.meta.requiresAuth)) {
        const token = localStorage.getItem("auth_token");
        if (token !== undefined && token !== null && token !== "") {
            const requiredRoles = to.matched
                .flatMap((record) => record.meta.roles || [])
                .filter(Boolean);

            if (requiredRoles.length > 0 && !roleManagement.hasAnyRole(requiredRoles)) {
                return next({ path: "/dashboard", replace: true });
            }
            return next();
        }
        return next({ path: "/login", replace: true });
    }

    return next();
}
