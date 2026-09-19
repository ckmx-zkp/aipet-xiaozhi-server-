package xiaozhi.modules.model.controller;
import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.apache.shiro.authz.annotation.RequiresPermissions;
import xiaozhi.common.utils.Result;
import xiaozhi.modules.model.service.ModelUsageService;

@RestController
@RequestMapping("/models/usage")
@RequiredArgsConstructor
public class ModelUsageController {
    private final ModelUsageService service;
    @GetMapping
    @RequiresPermissions("sys:role:superAdmin")
    public Result<List<Map<String,Object>>> list(){return new Result<List<Map<String,Object>>>().ok(service.getUsage());}
    @PostMapping("/report")
    public Result<Void> report(@RequestBody Map<String, Object> body) {
        String modelName = String.valueOf(body.getOrDefault("modelName", ""));
        int promptTokens = ((Number) body.getOrDefault("promptTokens", 0)).intValue();
        int completionTokens = ((Number) body.getOrDefault("completionTokens", 0)).intValue();
        int totalTokens = ((Number) body.getOrDefault("totalTokens", 0)).intValue();
        service.recordUsage(modelName, promptTokens, completionTokens, totalTokens);
        return new Result<Void>();
    }
    @PutMapping("/reminder/{key}")
    @RequiresPermissions("sys:role:superAdmin")
    public Result<Void> save(@PathVariable String key,@RequestBody Map<String,String> body){service.saveReminder(key,body.get("renewalDate"));return new Result<Void>();}
}
