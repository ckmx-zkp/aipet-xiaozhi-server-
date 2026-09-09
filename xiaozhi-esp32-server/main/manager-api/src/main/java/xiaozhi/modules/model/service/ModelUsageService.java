package xiaozhi.modules.model.service;

import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.jdbc.core.JdbcTemplate;
import lombok.RequiredArgsConstructor;
import com.fasterxml.jackson.databind.ObjectMapper;
import xiaozhi.modules.model.dao.ModelConfigDao;
import xiaozhi.common.exception.RenException;

@Service
@RequiredArgsConstructor
public class ModelUsageService {
    private final ModelConfigDao dao;
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final Map<String,Map<String,Object>> quotaCache = new HashMap<>();
    private final Map<String,Long> quotaCheckedAt = new HashMap<>();
    private long checkedAt;
    private List<Map<String,Object>> cached;
    private static final Set<String> LOCAL = Set.of("silero", "silero_vad", "funasr", "sherpa_onnx", "nointent", "function_call", "nomem", "mem_report_only", "mem_local_short", "intent_llm");
    private static class Group {
        String key, host, provider, credential;
        Map<String,Object> view = new LinkedHashMap<>();
        List<String> names = new ArrayList<>();
        int enabled, valid, invalid, unknown;
    }
    private Map<String,Group> groups() {
        Map<String,Group> groups = new LinkedHashMap<>();
        for (var model : dao.selectList(null)) {
            Map<String,Object> c = model.getConfigJson() == null ? Map.of() : model.getConfigJson();
            String provider = String.valueOf(c.getOrDefault("type", "unknown"));
            String url = String.valueOf(c.getOrDefault("base_url", c.getOrDefault("url", c.getOrDefault("api_url", ""))));
            String host = "";
            try { host = Optional.ofNullable(URI.create(url).getHost()).orElse(""); } catch (Exception ignored) {}
            String credential = "";
            for (String field : List.of("api_key", "api_password", "access_token", "appkey", "secret_key")) {
                Object value = c.get(field);
                if (value != null && !value.toString().isBlank()) { credential=value.toString(); break; }
            }
            String key;
            try { key = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest((provider+"|"+host+"|"+credential).getBytes(StandardCharsets.UTF_8))); }
            catch (Exception e) { throw new IllegalStateException(e); }
            Group g = groups.get(key);
            if (g == null) {
                g = new Group(); g.key=key; g.host=host; g.provider=provider; g.credential=credential;
                groups.put(key,g);
            }
            g.names.add(model.getModelName());
            if (Integer.valueOf(1).equals(model.getIsEnabled())) g.enabled++;
            if ("valid".equals(model.getValidityStatus())) g.valid++;
            else if ("invalid".equals(model.getValidityStatus())) g.invalid++;
            else g.unknown++;
        }
        Group clone=new Group();clone.key="voice-clone-resources";clone.host="";clone.provider="voice_clone";clone.credential="";
        clone.names.add("已分配的声音复刻资源");groups.put(clone.key,clone);
        return groups;
    }
    public synchronized List<Map<String,Object>> getUsage() {
        if (cached != null && System.currentTimeMillis()-checkedAt<60000) return cached;
        List<Map<String,Object>> result = new ArrayList<>();
        Map<String,String> renewals = new HashMap<>();
        jdbc.query("SELECT service_key,renewal_date FROM model_service_reminder", rs -> {
            if(rs.getDate(2)!=null) renewals.put(rs.getString(1),rs.getDate(2).toLocalDate().toString());
        });
        long now = System.currentTimeMillis();
        for (Group g : groups().values()) {
            Map<String,Object> v=g.view;
            v.put("serviceKey",g.key);v.put("models",g.names);v.put("enabledCount",g.enabled);
            v.put("validCount",g.valid);v.put("invalidCount",g.invalid);v.put("unknownCount",g.unknown);
            v.put("service",g.host.isBlank()?g.provider:g.host);v.put("checkedAt",now);
            v.put("status","manual");v.put("usage",List.of());v.put("warning",false);
            v.put("message","未核实当前凭据可查询官方账户用量，请在供应商后台核对；模型检测结果不代表余额。");
            v.put("consoleUrl","");
            if (g.host.equals("api.minimaxi.com") || g.host.equals("api.minimax.io")) {
                v.put("service","MiniMax");
                v.put("consoleUrl",g.host.endsWith("minimaxi.com")?"https://platform.minimaxi.com/console/usage":"https://platform.minimax.io/console/usage");
                queryMiniMax(g);
            } else if (g.provider.startsWith("doubao") || g.provider.startsWith("huoshan") || g.host.endsWith("volces.com")) {
                v.put("service","火山引擎 / 豆包");v.put("consoleUrl","https://console.volcengine.com/speech/service");
                v.put("message","当前语音 AppID/Access Token 不能代替云账户账单 AK/SK；用量、资源包与到期日在火山控制台核对。");
            } else if (g.host.endsWith("bigmodel.cn")) {
                v.put("service","智谱");v.put("consoleUrl","https://bigmodel.cn/usercenter/resourcepack");
                v.put("message","当前模型密钥的账户用量查询权限未核实，请在智谱后台查看余额与资源包。");
            } else if (g.provider.equals("edge") || LOCAL.contains(g.provider)) {
                v.put("status","not_applicable");v.put("message","本地/内置模块或 Edge 服务无本系统可查询的供应商账户账单；依赖模型费用请看对应服务。");
            }
            if(g.valid==0 && g.enabled==0 && !v.get("status").equals("ok"))
                v.put("message",v.get("message")+" 本组无已验证有效模型，建议先修复配置，不能据此判断欠费。");
            if(g.provider.equals("voice_clone")) {
                v.put("service","火山声音复刻2.0");v.put("resourceKind","voice_clone");v.put("alwaysVisible",true);
                v.put("consoleUrl","https://console.volcengine.com/speech/new/voices?projectName=default");
                var records=jdbc.queryForList("SELECT id,name,voice_id,remaining_training_times,provider_status,quota_checked_at FROM ai_voice_clone ORDER BY create_date DESC");
                v.put("resourceCount",records.size());List<Map<String,Object>> usage=new ArrayList<>();
                for(var record:records){
                    Map<String,Object> row=new LinkedHashMap<>();row.put("label",record.get("name")+" / "+record.get("voice_id"));row.put("cloneId",record.get("id"));
                    row.put("remainingTrainingTimes",record.get("remaining_training_times"));row.put("providerStatus",record.get("provider_status"));row.put("quotaCheckedAt",record.get("quota_checked_at"));usage.add(row);
                    if(record.get("remaining_training_times") instanceof Number n && n.intValue()<=1){v.put("warning",true);v.put("reminder","部分音色剩余训练次数不足，请刷新资源状态核对");}
                }
                v.put("usage",usage);v.put("status","manual");
                v.put("message",records.isEmpty()?"尚未分配音色资源。先在音色资源管理添加Speaker ID并分配给用户，再上传录音训练；不会自动购买或训练。":"显示最近主动查询的官方训练状态和剩余次数，不是合成余额；点击查询状态刷新。该接口不返回套餐到期日。");
            }
            String renewal=renewals.get(g.key);v.put("renewalDate",renewal);
            if(renewal!=null) {
                long days=java.time.temporal.ChronoUnit.DAYS.between(LocalDate.now(ZoneId.of("Asia/Shanghai")),LocalDate.parse(renewal));
                v.put("daysUntilRenewal",days);
                if(days<=7) { v.put("warning",true);v.put("reminder",days<0?"人工到期日已过，请核对续费":"距人工到期日剩余 "+days+" 天"); }
            }
            result.add(v);
        }
        result.sort(Comparator.comparingInt(v -> -(Integer)v.get("enabledCount")));
        checkedAt=now;cached=result;return result;
    }
    private void queryMiniMax(Group g) {
        long now=System.currentTimeMillis();
        if(quotaCache.containsKey(g.key) && now-quotaCheckedAt.get(g.key)<60000) {
            g.view.putAll(quotaCache.get(g.key)); return;
        }
        queryMiniMaxLive(g);
        Map<String,Object> evidence=new HashMap<>();
        for(String key:List.of("status","message","usage","warning","reminder","checkedAt"))
            if(g.view.containsKey(key)) evidence.put(key,g.view.get(key));
        quotaCache.put(g.key,evidence);quotaCheckedAt.put(g.key,now);
    }
    private void queryMiniMaxLive(Group g) {
        Map<String,Object> v=g.view;
        if (g.credential.isBlank() || g.valid==0) {v.put("message","当前没有有效凭据配置，未发起账户查询。");return;}
        try {
            String host=g.host.equals("api.minimaxi.com")?"www.minimaxi.com":"www.minimax.io";
            var req=HttpRequest.newBuilder(URI.create("https://"+host+"/v1/token_plan/remains"))
                .timeout(Duration.ofSeconds(8)).header("Authorization","Bearer "+g.credential).GET().build();
            var res=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build().send(req,HttpResponse.BodyHandlers.ofString());
            if(res.statusCode()!=200) {v.put("status","unavailable");v.put("message","用量接口 HTTP "+res.statusCode()+"；不代表模型 API 失效，请在后台核对套餐权限。");return;}
            var root=mapper.readTree(res.body());
            if(root.path("base_resp").path("status_code").asInt(-1)!=0 || !root.path("model_remains").isArray()) {
                v.put("status","unavailable");v.put("message","当前密钥未返回可用 Token Plan 额度，请在后台核对套餐。");return;
            }
            List<Map<String,Object>> usage=new ArrayList<>();
            for(var item:root.path("model_remains")) {
                for(String prefix:List.of("current_interval","current_weekly")) {
                    Map<String,Object> row=new LinkedHashMap<>();
                    row.put("label",item.path("model_name").asText()+ (prefix.endsWith("weekly")?" / 本周":" / 本周期"));
                    if(item.has(prefix+"_remaining_percent")) {
                        double remaining=item.path(prefix+"_remaining_percent").asDouble();
                        row.put("remainingPercent",remaining);
                        if(remaining<=20){v.put("warning",true);v.put("reminder","套餐剩余额度偏低，请检查重置时间或续费方案");}
                    }
                    long total=item.path(prefix+"_total_count").asLong();
                    if(total>0){row.put("total",total);row.put("used",item.path(prefix+"_usage_count").asLong());}
                    row.put("resetAt",item.path(prefix.endsWith("weekly")?"weekly_end_time":"end_time").asLong());
                    usage.add(row);
                }
            }
            v.put("usage",usage);v.put("status","ok");v.put("message","官方 Token Plan 实时配额；周期重置时间不是套餐到期日，百分比也不是账户现金余额。");
        } catch(Exception e) {
            if(e instanceof InterruptedException) Thread.currentThread().interrupt();
            v.put("status","unavailable");v.put("message","官方用量接口暂时不可达，请稍后刷新或在供应商后台核对。");
        }
    }
    public synchronized void saveReminder(String key, String date) {
        if(!groups().containsKey(key)) throw new RenException("服务配置已改变，请刷新后重试");
        LocalDate parsed=null;
        if(date!=null && !date.isBlank()) {
            try {parsed=LocalDate.parse(date);}catch(Exception e){throw new RenException("到期日格式应为 YYYY-MM-DD");}
        }
        jdbc.update("INSERT INTO model_service_reminder(service_key,renewal_date) VALUES (?,?) ON DUPLICATE KEY UPDATE renewal_date=VALUES(renewal_date),updated_at=CURRENT_TIMESTAMP",key,parsed==null?null:java.sql.Date.valueOf(parsed));
        cached=null;
    }
}
