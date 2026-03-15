package tr.org.lider.services;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;

import org.apache.directory.api.ldap.model.exception.LdapException;
import org.apache.directory.api.ldap.model.message.SearchScope;
import org.jivesoftware.smack.SmackException.NotConnectedException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.core.JsonGenerationException;
import com.fasterxml.jackson.databind.JsonMappingException;

import tr.org.lider.entities.AgentImpl;
import tr.org.lider.entities.AgentStatus;
import tr.org.lider.entities.CommandExecutionImpl;
import tr.org.lider.entities.CommandImpl;
import tr.org.lider.entities.OperationType;
import tr.org.lider.entities.PluginTask;
import tr.org.lider.entities.TaskImpl;
import tr.org.lider.ldap.DNType;
import tr.org.lider.ldap.LDAPServiceImpl;
import tr.org.lider.ldap.LdapEntry;
import tr.org.lider.message.service.IMessagingService;
import tr.org.lider.messaging.messages.ExecuteTaskMessageImpl;
import tr.org.lider.messaging.messages.FileServerConf;
import tr.org.lider.messaging.messages.ILiderMessage;
import tr.org.lider.repositories.AgentRepository;
import tr.org.lider.repositories.CommandExecutionRepository;
import tr.org.lider.repositories.TaskRepository;
import tr.org.lider.utils.IRestResponse;
import tr.org.lider.utils.ResponseFactoryService;
import tr.org.lider.utils.RestResponseStatus;

@Service
public class TaskService {

	Logger logger = LoggerFactory.getLogger(TaskService.class);

	@Autowired
	private LDAPServiceImpl ldapService;

	@Autowired
	private ConfigurationService configService;

	@Autowired
	private IMessagingService messagingService;

	@Autowired
	private CommandService commandService;

	@Autowired
	private ResponseFactoryService responseFactoryService;

	@Autowired
	private TaskRepository taskRepository;

	@Autowired
	private OperationLogService operationLogService;

	@Autowired
	private PluginTaskService pluginTaskService;

	@Autowired
	private AgentRepository agentRepository;

	@Autowired
	private CommandExecutionRepository commandExecutionRepository;

	@Autowired
	private TaskSchedulerService taskSchedulerService;

	@PersistenceContext
	private EntityManager entityManager;

	public IRestResponse execute(PluginTask request) {

		List<LdapEntry> targetEntries = getTargetList(request);

		if (targetEntries.isEmpty()) {
			return responseFactoryService.createResponse(
					RestResponseStatus.ERROR,
					"Yetkili olmadığınız bir hedefe görev gönderemezsiniz. İstemci bulunamadı.");
		}

		TaskImpl task = new TaskImpl(null, request.getPlugin(), request.getCommandId(), request.getParameterMap(), false,
				request.getCronExpression(), new Date(), null, request.isTaskParts());
		task = taskRepository.save(task);
		String commandIdForLog = task.getCommandClsId();
		List<PluginTask> pluginTask = pluginTaskService.findPluginTaskByCommandID(task.getCommandClsId());
		if (pluginTask != null && pluginTask.size() > 0) {
			commandIdForLog = pluginTask.get(0).getName();
		}
		String logMessage = "";
		String fragmentationLogMessage = "";
		if (request.getEntryList().get(0).getType().equals(DNType.GROUP)) {
			if (task.isTaskParts() == true) {
				fragmentationLogMessage = "[ " + commandIdForLog + " ] task was sent to the  [ "
						+ request.getEntryList().get(0).getDistinguishedName() + " ] client group in parts.";

			} else {

				logMessage = "[ " + commandIdForLog + " ] task sent to  [ "
						+ request.getEntryList().get(0).getDistinguishedName() + " ] client group.";
			}

		} else {
			logMessage = "[ " + commandIdForLog + " ] task sent to  [ "
					+ request.getEntryList().get(0).getDistinguishedName() + " ] client group.";
		}
		try {
			if (task.isTaskParts() == true) {
				operationLogService.saveOperationLog(OperationType.EXECUTE_TASK, fragmentationLogMessage,
						task.getParameterMapBlob(), task.getId(), null, null);
			} else {
				operationLogService.saveOperationLog(OperationType.EXECUTE_TASK, logMessage,
						task.getParameterMapBlob(), task.getId(), null, null);
			}
		} catch (Exception e) {
			e.printStackTrace();
		}

		List<String> uidList = new ArrayList<String>();

		for (LdapEntry entry : targetEntries) {
			if (ldapService.isAhenk(entry)) {
				String uid = resolveAgentUid(entry);
				if (uid != null && !uid.isBlank()) {
					uidList.add(uid);
				}
			}
		}

		CommandImpl command = null;

		try {
			command = new CommandImpl(null, null, task, request.getDnList(), request.getDnType(), uidList, findCommandOwnerJid(),
					((PluginTask) request).getActivationDate(), null, new Date(), null, false, false);

		} catch (JsonGenerationException e) {
			e.printStackTrace();
		} catch (JsonMappingException e) {
			e.printStackTrace();
		} catch (IOException e) {
			e.printStackTrace();
		}

		if (command != null) {
			commandService.addCommand(command);
		}

		if (targetEntries != null && !targetEntries.isEmpty()) {

			for (final LdapEntry entry : targetEntries) {

				boolean isAhenk = ldapService.isAhenk(entry);
				String uid = isAhenk ? resolveAgentUid(entry) : null;
				logger.info("DN type: {}, UID: {}", entry.getType().toString(), uid);
				uid = uid != null ? uid.trim() : null;

				Boolean isOnline = uid != null && messagingService.isRecipientOnline(getFullJid(uid));
				CommandExecutionImpl execution = new CommandExecutionImpl();
				Boolean isTaskSend = false;
				if (task.isTaskParts() == false) {
					isTaskSend = true;
				}
				execution = new CommandExecutionImpl(null, command, uid, entry.getType(), entry.getDistinguishedName(),
						new Date(), null, isOnline, isTaskSend);
				command.addCommandExecution(execution);

				ILiderMessage message = null;
				if (isAhenk) {
					if (uid == null || uid.isEmpty()) {
						logger.error("JID was null. Ignoring task: {} for agent: {}",
								new Object[] { task.toJson(), entry.getDistinguishedName() });
						continue;
					}
					logger.info("Sending task to agent with JID: {}", uid);

					String taskJsonString = null;
					try {
						taskJsonString = task.toJson();
					} catch (Exception e) {
						logger.error(e.getMessage(), e);
					}

					FileServerConf fileServerConf = request.getPlugin().isUsesFileTransfer()
							? configService.getFileServerConf(uid.toLowerCase()) : null;
					message = new ExecuteTaskMessageImpl(taskJsonString, uid, new Date(), fileServerConf);

					try {
						if (!task.isTaskParts()) {
							messagingService.sendMessage(message);
						}

					} catch (JsonGenerationException e) {
						e.printStackTrace();
					} catch (JsonMappingException e) {
						e.printStackTrace();
					} catch (NotConnectedException e) {
						e.printStackTrace();
					} catch (IOException e) {
						e.printStackTrace();
					}

				}
				commandService.addCommandExecution(execution);
			}
		}
		return responseFactoryService.createResponse(RestResponseStatus.OK, "Task Basarı ile Gonderildi.");
	}

	private List<LdapEntry> getTargetList(PluginTask request) {
		List<LdapEntry> targetEntries = new ArrayList<>();
		List<LdapEntry> ldapEntryGroups = new ArrayList<>();
		List<LdapEntry> selectedtEntries = request.getEntryList();
		for (LdapEntry ldapEntry : selectedtEntries) {
			if (ldapEntry.getType().equals(DNType.AHENK)) {
				String selectedUid = resolveAgentUid(ldapEntry);
				if (selectedUid == null || selectedUid.isBlank()) {
					logger.warn("Skipping selected agent without UID. DN={}", ldapEntry.getDistinguishedName());
					continue;
				}

				List<AgentImpl> agentList = agentRepository.findByJid(selectedUid);

				if (agentList != null && !agentList.isEmpty()) {
					AgentStatus agentStatus = agentList.get(0).getAgentStatus();

					if (agentStatus != null && agentStatus.equals(AgentStatus.Active)) {
						try {
							if (ldapService.getEntry(ldapEntry.getDistinguishedName(), new String[] {}) != null
									&& !ldapService.search(configService.getAgentLdapJidAttribute(), selectedUid,
											new String[] { configService.getAgentLdapJidAttribute() }).isEmpty()) {
								targetEntries.add(ldapEntry);
							}
						} catch (LdapException e) {
							throw new RuntimeException(e);
						}
					}
				}

			}
			if (ldapEntry.getType().equals(DNType.GROUP)) {
				List<String> dnList = ldapService.getGroupInGroupsTask(ldapEntry);
				ldapEntryGroups = ldapService.getLdapDnStringToEntry(dnList);
				for (LdapEntry ldapEntryGroup : ldapEntryGroups) {
					try {
						if (ldapService.getEntry(ldapEntry.getDistinguishedName(), new String[] {}) != null) {
							String[] members = ldapEntryGroup.getAttributesMultiValues().get("member");
							for (int i = 0; i < members.length; i++) {
								String dn = members[i];
								try {
									List<LdapEntry> member = ldapService.findSubEntries(dn, "(objectclass=pardusDevice)",
											new String[] { "*" }, SearchScope.OBJECT);
									if (member != null && member.size() > 0) {
										if (!ldapService.isExistInLdapEntry(targetEntries, member.get(0))) {
											if (!agentRepository.findByJid(member.get(0).getUid()).get(0).getAgentStatus()
													.equals(AgentStatus.Passive)) {
												targetEntries.add(member.get(0));
											}
										}
									}
								} catch (LdapException e) {
									e.printStackTrace();
								}
							}
						}
					} catch (LdapException e) {
						throw new RuntimeException(e);
					}
				}
			}
			if (ldapEntry.getType().equals(DNType.ORGANIZATIONAL_UNIT)) {

			}
		}

		return targetEntries;
	}

	private String resolveAgentUid(LdapEntry entry) {
		if (entry == null) {
			return null;
		}
		if (entry.getUid() != null && !entry.getUid().isBlank()) {
			return entry.getUid().trim();
		}

		String jidAttribute = configService.getAgentLdapJidAttribute();
		try {
			if (jidAttribute != null && entry.getAttributes() != null) {
				String uid = entry.get(jidAttribute);
				if (uid != null && !uid.isBlank()) {
					return uid.trim();
				}
			}
		} catch (Exception e) {
			logger.debug("Could not resolve UID from inline attributes for DN {}", entry.getDistinguishedName(), e);
		}

		String dn = entry.getDistinguishedName();
		if (dn == null || dn.isBlank()) {
			return null;
		}

		try {
			LdapEntry fullEntry = ldapService.getEntry(dn, new String[] { "*" });
			if (fullEntry == null) {
				return null;
			}
			if (fullEntry.getUid() != null && !fullEntry.getUid().isBlank()) {
				return fullEntry.getUid().trim();
			}
			if (jidAttribute != null && fullEntry.getAttributes() != null) {
				String uid = fullEntry.get(jidAttribute);
				if (uid != null && !uid.isBlank()) {
					return uid.trim();
				}
			}
		} catch (Exception e) {
			logger.warn("Could not resolve UID for DN {}", dn, e);
		}

		return null;
	}

	public String buildKey(String pluginName, String pluginVersion, String commandId) {
		StringBuilder key = new StringBuilder();
		key.append(pluginName).append(":").append(pluginVersion).append(":").append(commandId);
		return key.toString().toUpperCase(Locale.ENGLISH);
	}

	public String getFullJid(String jid) {
		if (jid == null || jid.isBlank()) {
			return jid;
		}
		String jidFinal = jid;
		if (jid.indexOf("@") < 0) {
			jidFinal = jid + "@" + configService.getXmppServiceName();
		}
		return jidFinal;
	}

	private String findCommandOwnerJid() {
		if (AuthenticationService.isLogged()) {
			logger.info(" task owner jid : " + AuthenticationService.getUser().getName());
			return AuthenticationService.getUser().getName();
		}
		return null;
	}

	public List<Object[]> findExecutedTaskWithCount() {
		List<Object[]> tasks = taskRepository.findExecutedTaskWithCount(AuthenticationService.getUserName());
		return tasks;
	}

}
