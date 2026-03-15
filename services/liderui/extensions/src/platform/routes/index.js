import { isFeatureEnabled } from "@/platform/feature-registry";

export function featureGate(route, feature) {
    if (isFeatureEnabled(feature)) {
        return route;
    }

    return {
        path: route.path,
        name: `${route.name}Disabled`,
        redirect: "/dashboard",
        meta: {
            requiresAuth: true,
        },
    };
}
