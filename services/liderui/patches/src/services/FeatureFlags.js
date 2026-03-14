const runtimeEnv = typeof window !== "undefined" && window.__ENV__ ? window.__ENV__ : {};

const disabledFeatures = new Set(
    String(runtimeEnv.UI_DISABLED_FEATURES || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean)
);

const roleFeatureMap = {
    ROLE_AD_SYNC: "ad",
    ROLE_CONKY_DEFINITION: "conky",
    ROLE_DEVICE_MANAGEMENT: "usb",
    ROLE_LOGIN_MANAGER: "ldap-login",
    ROLE_MANAGE_ROOT: "manage-root",
    ROLE_REMOTE_ACCESS: "remote-access",
    ROLE_SEND_MESSAGE: "conky",
    ROLE_SERVICE_MANAGEMENT: "service-management",
    ROLE_SESSION_POWER: "session-power",
    ROLE_USB_RULE: "usb",
    ROLE_FILE_TRANSFER: "file-transfer",
};

export function getFeatureProfile() {
    return runtimeEnv.LIDER_FEATURE_PROFILE || "v1-broad";
}

export function isFeatureEnabled(feature) {
    return !disabledFeatures.has(String(feature || "").trim());
}

export function isRoleEnabled(role) {
    const feature = roleFeatureMap[role];
    return feature ? isFeatureEnabled(feature) : true;
}

export function getDisabledFeatures() {
    return Array.from(disabledFeatures);
}
