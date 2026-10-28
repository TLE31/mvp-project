package example;

import java.util.List;

public class AttributeRepository {
    public List<Attribute> findAll() {
        return List.of(
                new Attribute("color", "sales"),
                new Attribute("size", "inventory"),
                new Attribute("region", "sales"));
    }
}
