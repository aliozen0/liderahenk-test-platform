package tr.org.lider.services;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import tr.org.lider.platform.inventory.AgentInventoryReconciler;

@Service
public class AgentInventorySyncService {

    private final AgentInventoryReconciler reconciler;

    public AgentInventorySyncService(AgentInventoryReconciler reconciler) {
        this.reconciler = reconciler;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void syncAgentsFromLdap() {
        reconciler.reconcileFromLdap();
    }
}
