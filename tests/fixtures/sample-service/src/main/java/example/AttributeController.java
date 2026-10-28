package example;

import java.util.List;

@org.springframework.web.bind.annotation.RestController
@org.springframework.web.bind.annotation.RequestMapping("/attributes")
public class AttributeController {
    private final AttributeService service;

    public AttributeController(AttributeService service) {
        this.service = service;
    }

    @org.springframework.web.bind.annotation.GetMapping
    public List<Attribute> list() {
        return service.filterByContext("sales");
    }
}
