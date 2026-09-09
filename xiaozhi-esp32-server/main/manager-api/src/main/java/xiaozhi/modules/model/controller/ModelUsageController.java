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
    @PutMapping("/reminder/{key}")
    @RequiresPermissions("sys:role:superAdmin")
    public Result<Void> save(@PathVariable String key,@RequestBody Map<String,String> body){service.saveReminder(key,body.get("renewalDate"));return new Result<Void>();}
}
