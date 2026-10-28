package example;

import java.util.List;

public class AttributeService {
    private final AttributeRepository repository;
    @org.springframework.beans.factory.annotation.Value("${business.context.enabled:false}")
    private boolean contextEnabled = true;

    public AttributeService(AttributeRepository repository) {
        this.repository = repository;
    }

    public List<Attribute> filterByContext(String context) {
        List<Attribute> attributes = repository.findAll();
        return contextEnabled ? attributes.stream().filter(item -> item.context().equals(context)).toList() : attributes;
    }
}
