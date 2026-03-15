package tr.org.lider.entities;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import jakarta.persistence.Temporal;
import jakarta.persistence.TemporalType;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.ObjectMapper;

import tr.org.lider.ldap.DNType;

@JsonIgnoreProperties({ "command" })
@Entity
@Table(name = "C_COMMAND_EXECUTION")
public class CommandExecutionImpl implements Serializable {

    private static final long serialVersionUID = 6762422648814400663L;

    @Id
    @GeneratedValue
    @Column(name = "COMMAND_EXECUTION_ID", unique = true, nullable = false)
    private Long id;

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "COMMAND_ID", nullable = false)
    private CommandImpl command;

    @Column(name = "UID")
    private String uid;

    @Column(name = "DN_TYPE", length = 1)
    private Integer dnType;

    @Column(name = "DN", length = 1000)
    private String dn;

    @Temporal(TemporalType.TIMESTAMP)
    @Column(name = "CREATE_DATE", nullable = false)
    @JsonFormat(pattern = "dd/MM/yyyy HH:mm:ss", timezone = "Europe/Istanbul")
    private Date createDate;

    @OneToMany(mappedBy = "commandExecution", cascade = CascadeType.ALL, fetch = FetchType.EAGER, orphanRemoval = false)
    @OrderBy("createDate DESC")
    private List<CommandExecutionResultImpl> commandExecutionResults = new ArrayList<>();

    @Column(name = "ONLINE")
    private boolean online;

    @Column(name = "COMMAND_SEND")
    private Boolean commandSend = false;

    public CommandExecutionImpl() {
    }

    public CommandExecutionImpl(
        Long id,
        CommandImpl command,
        String uid,
        DNType dnType,
        String dn,
        Date createDate,
        List<CommandExecutionResultImpl> commandExecutionResults,
        boolean online,
        Boolean commandSend
    ) {
        this.id = id;
        this.command = command;
        this.uid = uid;
        setDnType(dnType);
        this.dn = dn;
        this.createDate = createDate;
        this.commandExecutionResults = commandExecutionResults;
        this.online = online;
        this.commandSend = commandSend;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public CommandImpl getCommand() {
        return command;
    }

    public void setCommand(CommandImpl command) {
        this.command = command;
    }

    public String getUid() {
        return uid;
    }

    public void setUid(String uid) {
        this.uid = uid;
    }

    public DNType getDnType() {
        return DNType.getType(dnType);
    }

    public void setDnType(DNType dnType) {
        this.dnType = dnType == null ? null : dnType.getId();
    }

    public String getDn() {
        return dn;
    }

    public void setDn(String dn) {
        this.dn = dn;
    }

    public List<CommandExecutionResultImpl> getCommandExecutionResults() {
        return commandExecutionResults;
    }

    public void setCommandExecutionResults(List<CommandExecutionResultImpl> commandExecutionResults) {
        this.commandExecutionResults = commandExecutionResults;
    }

    public void addCommandExecutionResult(CommandExecutionResultImpl commandExecutionResult) {
        if (commandExecutionResults == null) {
            commandExecutionResults = new ArrayList<>();
        }
        if (commandExecutionResult.getCommandExecution() != this) {
            commandExecutionResult.setCommandExecution(this);
        }
        commandExecutionResults.add(commandExecutionResult);
    }

    public Date getCreateDate() {
        return createDate;
    }

    public void setCreateDate(Date createDate) {
        this.createDate = createDate;
    }

    public boolean isOnline() {
        return online;
    }

    public void setOnline(boolean online) {
        this.online = online;
    }

    public Boolean isCommanSend() {
        return commandSend != null ? commandSend : true;
    }

    public void setCommanSend(Boolean commandSend) {
        this.commandSend = commandSend != null ? commandSend : true;
    }

    public String toJson() {
        ObjectMapper mapper = new ObjectMapper();
        try {
            return mapper.writeValueAsString(this);
        } catch (Exception e) {
            e.printStackTrace();
        }
        return null;
    }
}
