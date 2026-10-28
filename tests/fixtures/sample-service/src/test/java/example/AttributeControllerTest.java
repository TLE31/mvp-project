package example;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class AttributeControllerTest {
    @Test
    void listsAttributes() {
        AttributeController controller = new AttributeController(new AttributeService(new AttributeRepository()));
        assertEquals(1, controller.list().size());
    }
}
