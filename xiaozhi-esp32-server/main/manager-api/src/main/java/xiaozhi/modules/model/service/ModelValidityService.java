package xiaozhi.modules.model.service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Date;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import xiaozhi.common.exception.RenException;
import xiaozhi.common.redis.RedisKeys;
import xiaozhi.common.redis.RedisUtils;
import xiaozhi.modules.model.dao.ModelConfigDao;
import xiaozhi.modules.model.entity.ModelConfigEntity;
import xiaozhi.modules.sys.service.SysParamsService;

@Service
@RequiredArgsConstructor
public class ModelValidityService {
    private final ModelConfigDao dao;
    private final RedisUtils redis;
    private final SysParamsService params;
    private final ObjectMapper mapper;
    @Value("${model.validation.url:http://xiaozhi-esp32-server:8003/internal/models/validate}")
    private String probeUrl;

    public static void requireValid(ModelConfigEntity entity) {
        if (entity == null || !"valid".equals(entity.getValidityStatus())) {
            throw new RenException("模型尚未验证有效，请先检测；无效或待验证模型不能启用或设为默认");
        }
    }

    public static void applyEditPolicy(ModelConfigEntity original, ModelConfigEntity updated) {
        boolean changed = !String.valueOf(original.getModelType()).equalsIgnoreCase(String.valueOf(updated.getModelType()))
                || !Objects.equals(original.getConfigJson(), updated.getConfigJson());
        if (changed) {
            updated.setValidityStatus("unknown");
            updated.setValidityReason("配置已修改，请重新检测");
            updated.setValidityCheckedAt(null);
            updated.setIsEnabled(0);
            updated.setIsDefault(0);
        } else if (Integer.valueOf(1).equals(updated.getIsEnabled())
                && !Integer.valueOf(1).equals(original.getIsEnabled())) {
            requireValid(original);
        }
    }

    public void clearCache(String id) {
        redis.delete(RedisKeys.getModelConfigById(id));
        redis.delete(RedisKeys.getModelNameById(id));
        redis.delete(RedisKeys.getServerConfigKey());
    }

    public ModelConfigEntity validate(String id) {
        ModelConfigEntity original = dao.selectById(id);
        if (original == null) throw new RenException("模型配置不存在");
        String secret = params.getValue("server.secret", true);
        if (secret == null || secret.isBlank()) throw new RenException("检测服务尚未配置认证");
        String status;
        String reason;
        try {
            Map<String, Object> probeConfig = new java.util.HashMap<>();
            if (original.getConfigJson() != null) probeConfig.putAll(original.getConfigJson());
            probeConfig.remove("_validation_dependency");
            String dependencyId = String.valueOf(probeConfig.getOrDefault("llm", ""));
            if (!dependencyId.isBlank()) {
                ModelConfigEntity dependency = dao.selectById(dependencyId);
                probeConfig.put("_validation_dependency", Map.of("status", dependency == null || dependency.getValidityStatus() == null ? "unknown" : dependency.getValidityStatus()));
            }
            String payload = mapper.writeValueAsString(Map.of("modelType", original.getModelType(), "config", probeConfig));
            HttpRequest request = HttpRequest.newBuilder(URI.create(probeUrl))
                    .timeout(Duration.ofSeconds(28)).header("Content-Type", "application/json")
                    .header("X-Server-Secret", secret).POST(HttpRequest.BodyPublishers.ofString(payload)).build();
            HttpResponse<String> response = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build()
                    .send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) throw new RenException("检测服务不可用或忙，请稍后重试（未更改原状态）");
            var result = mapper.readTree(response.body());
            status = result.path("status").asText();
            reason = result.path("reason").asText();
            if (!Set.of("valid", "invalid", "unknown").contains(status) || reason.length() > 255)
                throw new RenException("检测服务响应无效（未更改原状态）");
        } catch (RenException e) {
            throw e;
        } catch (Exception e) {
            if (e instanceof InterruptedException) Thread.currentThread().interrupt();
            throw new RenException("无法完成检测，请稍后重试（未更改原状态）");
        }
        // 乐观条件保证检测期间修改过配置时，旧结果不能覆盖新配置。
        UpdateWrapper<ModelConfigEntity> update = new UpdateWrapper<ModelConfigEntity>().eq("id", id)
                .eq("model_type", original.getModelType())
                .set("validity_status", status).set("validity_reason", reason).set("validity_checked_at", new Date());
        if (original.getConfigJson() == null) update.isNull("config_json");
        else update.apply("config_json = CAST({0} AS JSON)", original.getConfigJson().toString());
        if (!"valid".equals(status)) update.set("is_enabled", 0).set("is_default", 0);
        if (dao.update(null, update) != 1) throw new RenException("检测期间配置已改变，请重新检测");
        clearCache(id);
        ModelConfigEntity result = dao.selectById(id);
        result.setConfigJson(null);
        return result;
    }
}
