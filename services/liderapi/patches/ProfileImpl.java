package tr.org.lider.entities;

import java.io.IOException;
import java.io.Serializable;
import java.util.Date;
import java.util.Map;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.Lob;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.Temporal;
import jakarta.persistence.TemporalType;
import jakarta.persistence.Transient;

import org.hibernate.annotations.CreationTimestamp;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.core.JsonGenerationException;
import com.fasterxml.jackson.core.JsonParseException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@JsonIgnoreProperties({ "profileDataBlob" })
@Entity
@Table(name = "C_PROFILE")
public class ProfileImpl implements Serializable {

    private static final long serialVersionUID = 4891531016823828068L;

    @Id
    @GeneratedValue
    @Column(name = "PROFILE_ID", unique = true, nullable = false)
    private Long id;

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "PLUGIN_ID", nullable = false)
    private PluginImpl plugin;

    @Column(name = "LABEL", nullable = false)
    private String label;

    @Column(name = "DESCRIPTION")
    private String description;

    @Column(name = "OVERRIDABLE")
    private boolean overridable = true;

    @Column(name = "ACTIVE")
    private boolean active = true;

    @Column(name = "DELETED")
    private boolean deleted = false;

    @Lob
    @Column(name = "PROFILE_DATA", columnDefinition = "LONGBLOB")
    private byte[] profileDataBlob;

    @Transient
    private Map<String, Object> profileData;

    @Transient
    private String pluginName;

    @Temporal(TemporalType.TIMESTAMP)
    @Column(name = "CREATE_DATE", nullable = false, updatable = false)
    @CreationTimestamp
    @JsonFormat(pattern = "dd/MM/yyyy HH:mm:ss", timezone = "Europe/Istanbul")
    private Date createDate;

    @Temporal(TemporalType.TIMESTAMP)
    @Column(name = "MODIFY_DATE")
    @JsonFormat(pattern = "dd/MM/yyyy HH:mm:ss", timezone = "Europe/Istanbul")
    private Date modifyDate;

    public ProfileImpl() {
    }

    public ProfileImpl(
        Long id,
        PluginImpl plugin,
        String label,
        String description,
        boolean overridable,
        boolean active,
        boolean deleted,
        Map<String, Object> profileData,
        Date createDate,
        Date modifyDate
    ) {
        this.id = id;
        this.plugin = plugin;
        this.label = label;
        this.description = description;
        this.overridable = overridable;
        this.active = active;
        this.deleted = deleted;
        setProfileData(profileData);
        this.createDate = createDate;
        this.modifyDate = modifyDate;
    }

    public ProfileImpl(ProfileImpl profile) {
        this.id = profile.getId();
        this.label = profile.getLabel();
        this.description = profile.getDescription();
        this.overridable = profile.isOverridable();
        this.active = profile.isActive();
        this.deleted = profile.isDeleted();
        setProfileData(profile.getProfileData());
        this.createDate = profile.getCreateDate();
        this.modifyDate = profile.getModifyDate();
        if (profile.getPlugin() instanceof PluginImpl) {
            this.plugin = profile.getPlugin();
        }
    }

    public String getLabel() {
        return label;
    }

    public void setLabel(String label) {
        this.label = label;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public PluginImpl getPlugin() {
        return plugin;
    }

    public void setPlugin(PluginImpl plugin) {
        this.plugin = plugin;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public boolean isOverridable() {
        return overridable;
    }

    public void setOverridable(boolean overridable) {
        this.overridable = overridable;
    }

    public boolean isActive() {
        return active;
    }

    public void setActive(boolean active) {
        this.active = active;
    }

    public boolean isDeleted() {
        return deleted;
    }

    public void setDeleted(boolean deleted) {
        this.deleted = deleted;
    }

    public byte[] getProfileDataBlob() {
        if (profileDataBlob == null && profileData != null) {
            try {
                this.profileDataBlob = new ObjectMapper().writeValueAsBytes(profileData);
            } catch (JsonGenerationException | JsonMappingException e) {
                e.printStackTrace();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
        return profileDataBlob;
    }

    public void setProfileDataBlob(byte[] profileDataBlob) {
        this.profileDataBlob = profileDataBlob;
        try {
            this.profileData = new ObjectMapper().readValue(profileDataBlob, new TypeReference<Map<String, Object>>() {});
        } catch (JsonParseException | JsonMappingException e) {
            e.printStackTrace();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public Map<String, Object> getProfileData() {
        if (profileData == null && profileDataBlob != null) {
            try {
                this.profileData = new ObjectMapper().readValue(profileDataBlob, new TypeReference<Map<String, Object>>() {});
            } catch (JsonParseException | JsonMappingException e) {
                e.printStackTrace();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
        return profileData;
    }

    public void setProfileData(Map<String, Object> profileData) {
        this.profileData = profileData;
        try {
            this.profileDataBlob = new ObjectMapper().writeValueAsBytes(profileData);
        } catch (JsonGenerationException | JsonMappingException e) {
            e.printStackTrace();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public String getPluginName() {
        return pluginName;
    }

    public void setPluginName(String pluginName) {
        this.pluginName = pluginName;
    }

    public Date getCreateDate() {
        return createDate;
    }

    public void setCreateDate(Date createDate) {
        this.createDate = createDate;
    }

    public Date getModifyDate() {
        return modifyDate;
    }

    public void setModifyDate(Date modifyDate) {
        this.modifyDate = modifyDate;
    }
}
