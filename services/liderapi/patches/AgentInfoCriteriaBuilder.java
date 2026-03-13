package tr.org.lider.repositories;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.TypedQuery;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.CriteriaQuery;
import jakarta.persistence.criteria.Join;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;

import org.apache.commons.collections.CollectionUtils;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import tr.org.lider.dto.AgentDTO;
import tr.org.lider.entities.AgentImpl;
import tr.org.lider.entities.AgentPropertyImpl;

/*
 * AgentInfoCriteriaBuilder implements filtering agents with multiple data.
 * Filter can be applied over status(online, offline) registration date and agent properties
 * 
 * Patched: null-safe Optional handling throughout filterAgents()
 * 
 * @author <a href="mailto:hasan.kara@pardus.org.tr">Hasan Kara</a>
 * @author <a href="mailto:ebru.arslan@pardus.org.tr">Ebru Arslan</a>
 */

@Service
public class AgentInfoCriteriaBuilder {

	@PersistenceContext
	private EntityManager entityManager;

	/**
	 * Null-safe extraction from Optional&lt;String&gt;.
	 * Returns the contained value if present and non-empty, null otherwise.
	 */
	private static String optVal(Optional<String> opt) {
		if (opt != null && opt.isPresent()) {
			String v = opt.get();
			if (v != null && !v.trim().isEmpty()) {
				return v;
			}
		}
		return null;
	}

	public Page<AgentImpl> filterAgents(AgentDTO agentDTO,List<String> listOfOnlineUsers){
		
		PageRequest pageable = PageRequest.of(agentDTO.getPageNumber() - 1, agentDTO.getPageSize());

		CriteriaBuilder cb = entityManager.getCriteriaBuilder();
		//for filtered result count
		CriteriaBuilder cbCount = entityManager.getCriteriaBuilder();
		CriteriaQuery<Long> criteriaCount = cbCount.createQuery(Long.class);
		Root<AgentImpl> fromCount = criteriaCount.from(AgentImpl.class);
		criteriaCount.select(cbCount.count(fromCount));

		CriteriaQuery<AgentImpl> criteriaQuery = cb.createQuery(AgentImpl.class);
		Root<AgentImpl> from = criteriaQuery.from(AgentImpl.class);
		CriteriaQuery<AgentImpl> select = criteriaQuery.select(from);

		List<Predicate> predicates = new ArrayList<>();
		//for filtered result count
		List<Predicate> predicatesCount = new ArrayList<>();

		// --- Patched: null-safe Optional guards ---

		String dnVal = optVal(agentDTO.getDn());
		if(dnVal != null) {
			predicates.add(cb.like(from.get("dn").as(String.class), "%" + dnVal + "%"));
			predicatesCount.add(cbCount.like(fromCount.get("dn").as(String.class), "%" + dnVal + "%"));
		}

		if (agentDTO.getRegistrationStartDate() != null && agentDTO.getRegistrationStartDate().isPresent()) {
			predicates.add(cb.greaterThanOrEqualTo(from.get("createDate"), agentDTO.getRegistrationStartDate().get()));
			predicatesCount.add(cbCount.greaterThanOrEqualTo(fromCount.get("createDate"), agentDTO.getRegistrationStartDate().get()));
		}
		if (agentDTO.getRegistrationEndDate() != null && agentDTO.getRegistrationEndDate().isPresent()) {
			predicates.add(cb.lessThanOrEqualTo(from.get("createDate"), agentDTO.getRegistrationEndDate().get()));
			predicatesCount.add(cbCount.lessThanOrEqualTo(fromCount.get("createDate"), agentDTO.getRegistrationEndDate().get()));
		}

		String statusVal = optVal(agentDTO.getStatus());
		if("ONLINE".equals(statusVal)) {
			predicates.add(cb.in(from.get("jid"))
					.value(!CollectionUtils.isEmpty(listOfOnlineUsers)? listOfOnlineUsers : new ArrayList<String>(Arrays.asList(""))));
			predicatesCount.add(cbCount.in(fromCount.get("jid"))
					.value(!CollectionUtils.isEmpty(listOfOnlineUsers)? listOfOnlineUsers : new ArrayList<String>(Arrays.asList(""))));
		} else if("OFFLINE".equals(statusVal)) {
			predicates.add(
					cb.not(from.get("jid").in(
							!CollectionUtils.isEmpty(listOfOnlineUsers)? listOfOnlineUsers : new ArrayList<String>(Arrays.asList("")))));
			predicatesCount.add(
					cbCount.not(fromCount.get("jid").in(
							!CollectionUtils.isEmpty(listOfOnlineUsers)? listOfOnlineUsers : new ArrayList<String>(Arrays.asList("")))));
		}

		String hostnameVal = optVal(agentDTO.getHostname());
		if(hostnameVal != null) {
			predicates.add(cb.like(from.get("hostname").as(String.class), "%" + hostnameVal + "%"));
			predicatesCount.add(cbCount.like(fromCount.get("hostname").as(String.class), "%" + hostnameVal + "%") );
		}
		
		String macVal = optVal(agentDTO.getMacAddress());
		if(macVal != null) {
			predicates.add(cb.like(from.get("macAddresses").as(String.class), "%" + macVal + "%"));
			predicatesCount.add(cbCount.like(fromCount.get("macAddresses").as(String.class), "%" + macVal + "%") );
		}
		
		String ipVal = optVal(agentDTO.getIpAddress());
		if(ipVal != null) {
			predicates.add(cb.like(from.get("ipAddresses").as(String.class), "%" + ipVal + "%"));
			predicatesCount.add(cbCount.like(fromCount.get("ipAddresses").as(String.class), "%" + ipVal + "%") );
		}
		
		String brandVal = optVal(agentDTO.getBrand());
		if(brandVal != null) {
			Join<AgentImpl, AgentPropertyImpl> properties = from.join("properties");
			Predicate namePredicate = cb.like(properties.get("propertyName").as(String.class), "hardware.baseboard.manufacturer");
			Predicate valuePredicate = cb.like(properties.get("propertyValue").as(String.class), brandVal);
			predicates.add(cb.and(namePredicate, valuePredicate));

			//for count 
			Join<AgentImpl, AgentPropertyImpl> propertiesCount = fromCount.join("properties");
			Predicate namePredicateCount = cbCount.like(propertiesCount.get("propertyName").as(String.class), "hardware.baseboard.manufacturer");
			Predicate valuePredicateCount = cbCount.like(propertiesCount.get("propertyValue").as(String.class), brandVal);
			predicatesCount.add(cbCount.and(namePredicateCount, valuePredicateCount));
		}

		String modelVal = optVal(agentDTO.getModel());
		if(modelVal != null) {
			Join<AgentImpl, AgentPropertyImpl> properties = from.join("properties");
			Predicate namePredicate = cb.like(properties.get("propertyName").as(String.class), "hardware.baseboard.productName");
			Predicate valuePredicate = cb.like(properties.get("propertyValue").as(String.class), modelVal);
			predicates.add(cb.and(namePredicate, valuePredicate));

			//for count 
			Join<AgentImpl, AgentPropertyImpl> propertiesCount = fromCount.join("properties");
			Predicate namePredicateCount = cbCount.like(propertiesCount.get("propertyName").as(String.class), "hardware.baseboard.productName");
			Predicate valuePredicateCount = cbCount.like(propertiesCount.get("propertyValue").as(String.class), modelVal);
			predicatesCount.add(cbCount.and(namePredicateCount, valuePredicateCount));
		}

		String procVal = optVal(agentDTO.getProcessor());
		if(procVal != null) {
			Join<AgentImpl, AgentPropertyImpl> properties = from.join("properties");
			Predicate namePredicate = cb.like(properties.get("propertyName").as(String.class), "processor");
			Predicate valuePredicate = cb.like(properties.get("propertyValue").as(String.class), procVal);
			predicates.add(cb.and(namePredicate, valuePredicate));

			//for count 
			Join<AgentImpl, AgentPropertyImpl> propertiesCount = fromCount.join("properties");
			Predicate namePredicateCount = cbCount.like(propertiesCount.get("propertyName").as(String.class), "processor");
			Predicate valuePredicateCount = cbCount.like(propertiesCount.get("propertyValue").as(String.class), procVal);
			predicatesCount.add(cbCount.and(namePredicateCount, valuePredicateCount));
		}
		
		String osVal = optVal(agentDTO.getOsVersion());
		if(osVal != null && !"null".equals(osVal)) {
			Join<AgentImpl, AgentPropertyImpl> properties = from.join("properties");
			Predicate namePredicate = cb.like(properties.get("propertyName").as(String.class), "os.version");
			Predicate valuePredicate = cb.like(properties.get("propertyValue").as(String.class), osVal);
			predicates.add(cb.and(namePredicate, valuePredicate));

			//for count 
			Join<AgentImpl, AgentPropertyImpl> propertiesCount = fromCount.join("properties");
			Predicate namePredicateCount = cbCount.like(propertiesCount.get("propertyName").as(String.class), "os.version");
			Predicate valuePredicateCount = cbCount.like(propertiesCount.get("propertyValue").as(String.class), osVal);
			predicatesCount.add(cbCount.and(namePredicateCount, valuePredicateCount));
		}
		
		String agentVerVal = optVal(agentDTO.getAgentVersion());
		if(agentVerVal != null) {
			Join<AgentImpl, AgentPropertyImpl> properties = from.join("properties");
			Predicate namePredicate = cb.like(properties.get("propertyName").as(String.class), "agentVersion");
			Predicate valuePredicate = cb.like(properties.get("propertyValue").as(String.class), agentVerVal);
			predicates.add(cb.and(namePredicate, valuePredicate));

			//for count 
			Join<AgentImpl, AgentPropertyImpl> propertiesCount = fromCount.join("properties");
			Predicate namePredicateCount = cbCount.like(propertiesCount.get("propertyName").as(String.class), "agentVersion");
			Predicate valuePredicateCount = cbCount.like(propertiesCount.get("propertyValue").as(String.class), agentVerVal);
			predicatesCount.add(cbCount.and(namePredicateCount, valuePredicateCount));
		}
		
		String diskVal = optVal(agentDTO.getDiskType());
		if(diskVal != null && !"ALL".equals(diskVal)) {
			
			Join<AgentImpl, AgentPropertyImpl> properties = from.join("properties");
			Predicate namePredicate = cb.like(properties.get("propertyName").as(String.class), diskVal);
			predicates.add(namePredicate);

			//for count 
			Join<AgentImpl, AgentPropertyImpl> propertiesCount = fromCount.join("properties");
			Predicate namePredicateCount = cbCount.like(propertiesCount.get("propertyName").as(String.class), diskVal);
			predicatesCount.add(namePredicateCount);
		}

		// Patched: agentStatus filter — skip "ALL", only filter on specific integer status
		String agentStatusVal = optVal(agentDTO.getAgentStatus());
		if(agentStatusVal != null && !"ALL".equals(agentStatusVal)) {
			try {
				Integer statusInt = Integer.valueOf(agentStatusVal);
				predicates.add(cb.equal(from.get("agentStatus"), statusInt));
				predicatesCount.add(cb.equal(fromCount.get("agentStatus"), statusInt));
			} catch (NumberFormatException ignored) {
				// non-numeric status value — skip filter
			}
		}

		criteriaQuery.where(predicates.toArray(new Predicate[predicates.size()]));
		criteriaQuery.orderBy(cb.desc(from.get("createDate")));
		Long count = count(cbCount, predicatesCount, criteriaCount);

		TypedQuery<AgentImpl> typedQuery = entityManager.createQuery(select);
		typedQuery.setFirstResult((agentDTO.getPageNumber() - 1) * agentDTO.getPageSize());
		if(agentDTO.getPageNumber() * agentDTO.getPageSize() > count) {
			typedQuery.setMaxResults((int) (count%agentDTO.getPageSize()));
		} else {
			typedQuery.setMaxResults(agentDTO.getPageSize());
		}
		
		Page<AgentImpl> agents = new PageImpl<AgentImpl>(typedQuery.getResultList(), pageable, count);

		return agents;
		
	}

	/*
	 * get count of filtered data for paging
	 */
	public Long count(CriteriaBuilder builder, List<Predicate> restrictions, CriteriaQuery<Long> criteria ) {
		criteria.where(restrictions.toArray(new Predicate[restrictions.size()]));
		TypedQuery<Long> query = entityManager.createQuery(criteria);
		return query.getSingleResult();
	}
}