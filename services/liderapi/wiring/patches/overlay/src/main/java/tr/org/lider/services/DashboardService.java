package tr.org.lider.services;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;

import org.apache.directory.api.ldap.model.exception.LdapException;
import org.apache.directory.api.ldap.model.message.SearchScope;
import org.springframework.stereotype.Service;

import tr.org.lider.ldap.LDAPServiceImpl;
import tr.org.lider.platform.dashboard.DashboardComputerMetricsProvider;

@Service
public class DashboardService {

    private final ConfigurationService configurationService;
    private final LDAPServiceImpl ldapService;
    private final CommandService commandService;
    private final OperationLogService operationLogService;
    private final AgentService agentService;
    private final TaskService taskService;
    private final DashboardComputerMetricsProvider dashboardComputerMetricsProvider;

    public DashboardService(
        ConfigurationService configurationService,
        LDAPServiceImpl ldapService,
        CommandService commandService,
        OperationLogService operationLogService,
        AgentService agentService,
        TaskService taskService,
        DashboardComputerMetricsProvider dashboardComputerMetricsProvider
    ) {
        this.configurationService = configurationService;
        this.ldapService = ldapService;
        this.commandService = commandService;
        this.operationLogService = operationLogService;
        this.agentService = agentService;
        this.taskService = taskService;
        this.dashboardComputerMetricsProvider = dashboardComputerMetricsProvider;
    }

    public HashMap<String, Object> getDashboardReport() {
        HashMap<String, Object> model = new HashMap<>();
        int countOfLDAPUsers = 0;

        try {
            countOfLDAPUsers = ldapService.findSubEntries(
                configurationService.getLdapRootDn(),
                "(objectclass=pardusAccount)",
                new String[] { "*" },
                SearchScope.SUBTREE
            ).size();
        } catch (LdapException e) {
            e.printStackTrace();
        }

        model.put("totalComputerNumber", dashboardComputerMetricsProvider.totalComputerCount());
        model.put("totalUserNumber", countOfLDAPUsers);
        model.put("totalSentTaskNumber", commandService.getTotalCountOfSentTasks());
        model.put("totalAssignedPolicyNumber", commandService.getTotalCountOfAssignedPolicy());
        model.put("totalOnlineComputerNumber", dashboardComputerMetricsProvider.totalOnlineComputerCount());

        List<String> dateRanges = new ArrayList<>();
        List<Integer> dateRangeValuesAgent = new ArrayList<>();
        int monthCount = 24;

        for (int i = monthCount - 1; i >= 0; i--) {
            Calendar startDate = Calendar.getInstance();
            startDate.add(Calendar.MONTH, -i);
            startDate.set(Calendar.HOUR, 0);
            startDate.set(Calendar.MINUTE, 0);
            startDate.set(Calendar.SECOND, 0);
            startDate.set(Calendar.MILLISECOND, 0);
            startDate.set(Calendar.DAY_OF_MONTH, startDate.getActualMinimum(Calendar.DAY_OF_MONTH));

            Calendar endDate = Calendar.getInstance();
            endDate.add(Calendar.MONTH, -i);
            endDate.set(Calendar.HOUR, 0);
            endDate.set(Calendar.MINUTE, 0);
            endDate.set(Calendar.SECOND, 0);
            endDate.set(Calendar.MILLISECOND, 0);
            endDate.set(Calendar.DAY_OF_MONTH, endDate.getActualMaximum(Calendar.DAY_OF_MONTH));
            endDate.add(Calendar.DATE, 1);

            String monthNameForStartDate = startDate.getDisplayName(Calendar.MONTH, Calendar.LONG, Locale.forLanguageTag("tr-TR"));
            dateRangeValuesAgent.add(agentService.getCountByCreateDate(startDate.getTime(), endDate.getTime()));
            dateRanges.add(monthNameForStartDate + "-" + startDate.get(Calendar.YEAR));
        }
        model.put("dateRangeValuesAgent", dateRangeValuesAgent);
        model.put("dateRanges", dateRanges);

        Calendar nowDate = Calendar.getInstance();
        nowDate.set(Calendar.HOUR, 0);
        nowDate.set(Calendar.MINUTE, 0);
        nowDate.set(Calendar.SECOND, 0);
        nowDate.set(Calendar.MILLISECOND, 0);
        nowDate.set(Calendar.HOUR_OF_DAY, 0);
        model.put("totalRegisteredComputerTodayNumber", agentService.getCountByTodayCreateDate(nowDate.getTime()));
        model.put("totalSessionsTodayNumber", agentService.getCountByTodayLastLogin(nowDate.getTime()));

        String userDn = AuthenticationService.getDn();
        model.put("liderConsoleLastActivity", operationLogService.getLastActivityByUserIdDescLimitTen(userDn));
        model.put("userTasks", taskService.findExecutedTaskWithCount());
        return model;
    }
}
