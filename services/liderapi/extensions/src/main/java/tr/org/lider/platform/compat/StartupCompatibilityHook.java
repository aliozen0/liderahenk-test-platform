package tr.org.lider.platform.compat;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class StartupCompatibilityHook implements PlatformCompatibilityHook {

    private static final Logger logger = LoggerFactory.getLogger(StartupCompatibilityHook.class);

    @Value("${LIDER_FEATURE_PROFILE:v1-broad}")
    private String featureProfile;

    @Override
    public void apply() {
        logger.info("Platform compatibility hooks active for feature profile {}", featureProfile);
    }
}
