package tr.org.lider.platform.catalog;

import java.util.List;
import java.util.Set;

public interface FeatureCatalogProvider {

    Set<String> activePlugins();

    Set<String> activeTaskCommandIds();

    Set<String> activeProfilePages();

    List<String> activeTaskPages();
}
