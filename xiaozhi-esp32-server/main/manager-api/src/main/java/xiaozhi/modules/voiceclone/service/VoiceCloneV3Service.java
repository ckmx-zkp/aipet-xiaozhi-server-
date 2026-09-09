package xiaozhi.modules.voiceclone.service;

import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import java.util.regex.Pattern;
import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import com.baomidou.mybatisplus.core.conditions.update.UpdateWrapper;
import com.fasterxml.jackson.databind.*;
import xiaozhi.common.exception.RenException;
import xiaozhi.modules.model.dao.ModelConfigDao;
import xiaozhi.modules.voiceclone.dao.VoiceCloneDao;
import xiaozhi.modules.voiceclone.entity.VoiceCloneEntity;

@Service
@RequiredArgsConstructor
public class VoiceCloneV3Service {
    private final VoiceCloneDao dao;
    private final ModelConfigDao models;
    private final ObjectMapper mapper;
    private static final Pattern CUSTOM = Pattern.compile("[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]");
    private static final Pattern RESERVED = Pattern.compile("(?i)^((S_|ICL_|MIX_|DiT_|BV)|[a-z]{2}_|(wvae|moon|mercury|venus|earth|mars|jupiter|saturn|uranus|neptune|pluto|umm)_).*|.*_(bigtts|bigtts_cc|tob|cs_tob|streaming)$");
    public static boolean validSpeaker(String id) {
        return id!=null && (id.matches("S_[A-Za-z0-9_-]+") || (CUSTOM.matcher(id).matches() && !RESERVED.matcher(id).matches()));
    }
    public static Map<String,Object> speakerBody(String id) {
        if(!validSpeaker(id))throw new RenException("音色ID格式无效，请填写已购买的S_音色或符合官方规则的自定义ID");
        Map<String,Object> body=new LinkedHashMap<>();
        body.put("speaker_id",id.startsWith("S_")?id:"custom_speaker_id");
        if(!id.startsWith("S_"))body.put("custom_speaker_id",id);
        return body;
    }
    public static Map<String,Object> trainingBody(VoiceCloneEntity entity) {
        byte[] audio=entity.getVoice();
        if(audio==null || audio.length<12 || audio.length>10*1024*1024)throw new RenException("请先上传不超过10MB的WAV录音");
        if(!new String(audio,0,4,java.nio.charset.StandardCharsets.US_ASCII).equals("RIFF") || !new String(audio,8,4,java.nio.charset.StandardCharsets.US_ASCII).equals("WAVE"))throw new RenException("录音不是有效WAV格式，请重新上传转换");
        Map<String,Object> body=speakerBody(entity.getVoiceId());
        body.put("audio",Map.of("data",Base64.getEncoder().encodeToString(audio),"format","wav"));
        String lang=Optional.ofNullable(entity.getLanguages()).orElse("中文").toLowerCase();
        Map<String,Integer> languages=Map.ofEntries(Map.entry("中文",0),Map.entry("zh",0),Map.entry("zh-cn",0),Map.entry("zh_cn",0),Map.entry("cn",0),Map.entry("english",1),Map.entry("英文",1),Map.entry("英语",1),Map.entry("en",1),Map.entry("日语",2),Map.entry("ja",2),Map.entry("西班牙语",3),Map.entry("es",3),Map.entry("德语",6),Map.entry("de",6),Map.entry("法语",7),Map.entry("fr",7),Map.entry("韩语",8),Map.entry("ko",8));
        if(!languages.containsKey(lang))throw new RenException("当前复刻页面暂不支持此语种，请选择已支持的单一语种");
        body.put("language",languages.get(lang));return body;
    }
    public Map<String,Object> refresh(String id) {
        VoiceCloneEntity entity=requireEntity(id);
        if(Integer.valueOf(1).equals(entity.getTrainStatus()) && entity.getQuotaCheckedAt()!=null && System.currentTimeMillis()-entity.getQuotaCheckedAt().getTime()<30000)
            throw new RenException("训练请求仍在处理中，请稍后刷新状态");
        return apply(entity,request(entity,"get_voice",speakerBody(entity.getVoiceId()),false));
    }
    public Map<String,Object> train(String id) {
        VoiceCloneEntity entity=requireEntity(id);Map<String,Object> body=trainingBody(entity);
        configuration(entity);
        if(Integer.valueOf(0).equals(entity.getRemainingTrainingTimes()))throw new RenException("剩余训练次数为0，请先刷新状态或在火山控制台核对资源");
        // 单条原子更新避免双击和并发请求消耗多次训练额度。
        if(dao.update(null,new UpdateWrapper<VoiceCloneEntity>().eq("id",id).ne("train_status",1).set("train_status",1).set("quota_checked_at",new Date()).set("train_error","训练请求已发送，结果未确认前请勿重复训练"))!=1)
            throw new RenException("已有训练请求未完成，请刷新状态后再操作");
        try {return apply(entity,request(entity,"voice_clone",body,true));}
        catch(RenException e) {
            // 网络超时可能已被供应商接收，保留训练中状态供后续只读查询确认。
            dao.update(null,new UpdateWrapper<VoiceCloneEntity>().eq("id",id).set("train_error",e.getMsg()));throw e;
        }
    }
    private VoiceCloneEntity requireEntity(String id) {
        VoiceCloneEntity entity=dao.selectById(id);if(entity==null)throw new RenException("音色资源不存在");return entity;
    }
    private cn.hutool.json.JSONObject configuration(VoiceCloneEntity entity) {
        var model=models.selectById(entity.getModelId());
        if(model==null || model.getConfigJson()==null || !"huoshan_double_stream".equals(model.getConfigJson().getStr("type")))throw new RenException("请选择火山双向流式模型的音色资源");
        var c=model.getConfigJson();
        if(c.getStr("voice_clone_api_key","").isBlank() && (c.getStr("appid","").isBlank() || c.getStr("access_token","").isBlank()))throw new RenException("请配置复刻API Key或原控制台AppID/Access Token");
        return c;
    }
    private JsonNode request(VoiceCloneEntity entity,String action,Map<String,Object> body,boolean training) {
        var c=configuration(entity);
        try {
            var builder=HttpRequest.newBuilder(URI.create("https://openspeech.bytedance.com/api/v3/tts/"+action)).timeout(Duration.ofSeconds(training?25:8))
                .header("Content-Type","application/json").header("X-Api-Request-Id",UUID.randomUUID().toString());
            String key=c.getStr("voice_clone_api_key","");
            if(!key.isBlank())builder.header("X-Api-Key",key);
            else {
                String app=c.getStr("appid",""),token=c.getStr("access_token","");
                if(app.isBlank() || token.isBlank())throw new RenException("请配置复刻API Key或原控制台AppID/Access Token");
                String resource=c.getStr("voice_clone_resource_id","");
                builder.header("X-Api-App-Key",app).header("X-Api-Access-Key",token).header("X-Api-Resource-Id",resource.isBlank()?"seed-icl-2.0":resource);
            }
            var response=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build().send(builder.POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body))).build(),HttpResponse.BodyHandlers.ofString());
            JsonNode result=mapper.readTree(response.body());int code=result.path("code").asInt(0);
            if(response.statusCode()!=200 || (code!=0 && code!=20000000)) {
                if(training)dao.update(null,new UpdateWrapper<VoiceCloneEntity>().eq("id",entity.getId()).set("train_status",3));
                throw new RenException("火山复刻请求被拒绝（HTTP "+response.statusCode()+"，错误码 "+code+"）；请核对音色资源、权限或剩余训练次数");
            }
            return result;
        }catch(RenException e){throw e;}
        catch(Exception e){if(e instanceof InterruptedException)Thread.currentThread().interrupt();throw new RenException(training?"训练结果未确认，请稍后刷新状态，不要立即重复训练":"音色查询暂未完成，请稍后重试");}
    }
    private Map<String,Object> apply(VoiceCloneEntity entity,JsonNode result) {
        int status=result.path("status").asInt(-1);if(status<0 || status>4)throw new RenException("火山未返回可识别的训练状态，请稍后查询");
        UpdateWrapper<VoiceCloneEntity> update=new UpdateWrapper<VoiceCloneEntity>().eq("id",entity.getId()).set("provider_status",status)
            .set("train_status",status==4?2:status).set("quota_checked_at",new Date()).set("train_error",status==3?"火山返回训练失败，请检查录音及资源":"");
        if(result.has("available_training_times") && result.path("available_training_times").canConvertToInt()) update.set("remaining_training_times",result.path("available_training_times").asInt());
        String demo=result.path("demo_audio").asText("");
        if(demo.isBlank() && result.path("speaker_status").isArray())for(JsonNode speaker:result.path("speaker_status"))if(speaker.path("model_type").asInt()==5){demo=speaker.path("demo_audio").asText("");break;}
        if(!demo.startsWith("https://") || demo.length()>2048)demo="";
        update.set("demo_audio_url",demo);dao.update(null,update);
        var saved=dao.selectById(entity.getId());Map<String,Object> view=new LinkedHashMap<>();
        view.put("trainStatus",saved.getTrainStatus());view.put("providerStatus",saved.getProviderStatus());view.put("remainingTrainingTimes",saved.getRemainingTrainingTimes());view.put("quotaCheckedAt",saved.getQuotaCheckedAt());view.put("demoAudioUrl",saved.getDemoAudioUrl());return view;
    }
}
