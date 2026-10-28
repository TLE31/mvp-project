package example;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

class AttributeServiceTest {
    @Test
    void filtersByContext() {
        AttributeRepository repository = new AttributeRepository();
        AttributeService service = new AttributeService(repository);
        assertEquals(1, service.filterByContext("inventory").size());
    }
}
