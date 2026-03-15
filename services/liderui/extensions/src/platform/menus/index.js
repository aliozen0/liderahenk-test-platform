import { filterByFeatureState } from "@/platform/feature-registry";

export function filterMenuEntries(entries = []) {
    return filterByFeatureState(entries, (entry) => entry?.feature);
}
