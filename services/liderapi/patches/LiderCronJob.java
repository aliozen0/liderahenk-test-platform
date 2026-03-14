package tr.org.lider;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import tr.org.lider.entities.AgentImpl;
import tr.org.lider.entities.AgentStatus;
import tr.org.lider.message.service.IMessagingService;
import tr.org.lider.repositories.AgentRepository;
import tr.org.lider.services.ConfigurationService;
import tr.org.lider.services.TaskSchedulerService;

@Component
@EnableScheduling
public class LiderCronJob {

    @Autowired
    private AgentRepository agentRepository;

    @Autowired
    private IMessagingService messagingService;

    @Autowired
    private ConfigurationService configurationService;

    @Autowired
    private TaskSchedulerService taskScheduledService;

    private final Logger logger = LoggerFactory.getLogger(this.getClass());

    @Scheduled(cron = "0 55 10 * * ?")
    public void dailyCronJob() {
        if (configurationService.getMachineEventStatus() != true) {
            return;
        }

        Date today = new Date();
        List<AgentImpl> agentsEventDate = agentRepository.findAll();

        for (AgentImpl agent : agentsEventDate) {
            if (messagingService.isRecipientOnline(agent.getJid())) {
                continue;
            }

            Date eventDate = agent.getEventDate();
            if (eventDate == null) {
                logger.info("Event date is null for agent: {}", agent.getId());
                continue;
            }

            LocalDate todayLocalDate = today.toInstant().atZone(ZoneId.systemDefault()).toLocalDate();
            LocalDate dbEventDate = eventDate.toInstant().atZone(ZoneId.systemDefault()).toLocalDate();
            long daysDifference = ChronoUnit.DAYS.between(todayLocalDate, dbEventDate);

            if (daysDifference > -configurationService.getMachineEventDay()) {
                agent.setAgentStatus(AgentStatus.Active);
            } else {
                agent.setAgentStatus(AgentStatus.Passive);
            }
            agentRepository.save(agent);
        }

        logger.info("Executed cron job for machine update");
    }

    @Scheduled(cron = "0 */20 * * * ?")
    public void taskJob() {
        try {
            taskScheduledService.sendScheduledTaskMesasage();
        } catch (IndexOutOfBoundsException e) {
            logger.debug("Scheduled task queue is empty, skipping dispatch.");
        } catch (Throwable t) {
            logger.warn("Scheduled task dispatch failed: {}", t.getMessage());
        }
    }
}
