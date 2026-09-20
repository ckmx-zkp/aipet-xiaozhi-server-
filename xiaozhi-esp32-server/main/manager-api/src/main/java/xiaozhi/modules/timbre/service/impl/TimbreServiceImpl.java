package xiaozhi.modules.timbre.service.impl;

import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;

import cn.hutool.core.collection.CollectionUtil;
import lombok.AllArgsConstructor;
import xiaozhi.common.constant.Constant;
import xiaozhi.common.exception.ErrorCode;
import xiaozhi.common.page.PageData;
import xiaozhi.common.redis.RedisKeys;
import xiaozhi.common.redis.RedisUtils;
import xiaozhi.common.service.impl.BaseServiceImpl;
import xiaozhi.common.utils.ConvertUtils;
import xiaozhi.common.utils.MessageUtils;
import xiaozhi.modules.model.dto.VoiceDTO;
import xiaozhi.modules.security.user.SecurityUser;
import xiaozhi.modules.timbre.dao.TimbreDao;
import xiaozhi.modules.timbre.dto.TimbreDataDTO;
import xiaozhi.modules.timbre.dto.TimbrePageDTO;
import xiaozhi.modules.timbre.entity.TimbreEntity;
import xiaozhi.modules.timbre.service.TimbreService;
import xiaozhi.modules.timbre.vo.TimbreDetailsVO;
import xiaozhi.modules.voiceclone.dao.VoiceCloneDao;
import xiaozhi.modules.voiceclone.entity.VoiceCloneEntity;

/**
 * 音色的业务层的实现
 * 
 * @author zjy
 * @since 2025-3-21
 */
@AllArgsConstructor
@Service
public class TimbreServiceImpl extends BaseServiceImpl<TimbreDao, TimbreEntity> implements TimbreService {

    private static final Pattern LANGUAGE_SEPARATOR = Pattern.compile("[、；;,，]");

    private final TimbreDao timbreDao;
    private final VoiceCloneDao voiceCloneDao;
    private final RedisUtils redisUtils;

    @Override
    public PageData<TimbreDetailsVO> page(TimbrePageDTO dto) {
        Map<String, Object> params = new HashMap<String, Object>();
        params.put(Constant.PAGE, dto.getPage());
        params.put(Constant.LIMIT, dto.getLimit());
        IPage<TimbreEntity> page = baseDao.selectPage(
                getPage(params, null, true),
                // 定义查询条件
                new QueryWrapper<TimbreEntity>()
                        // 必须按照ttsID查找
                        .eq("tts_model_id", dto.getTtsModelId())
                        // 如果有音色名字，按照音色名模糊查找
                        .like(StringUtils.isNotBlank(dto.getName()), "name", dto.getName()));

        return getPageData(page, TimbreDetailsVO.class);
    }

    @Override
    public TimbreDetailsVO get(String timbreId) {
        if (StringUtils.isBlank(timbreId)) {
            return null;
        }

        // 先从Redis获取缓存
        String key = RedisKeys.getTimbreDetailsKey(timbreId);
        TimbreDetailsVO cachedDetails = (TimbreDetailsVO) redisUtils.get(key);
        if (cachedDetails != null) {
            return cachedDetails;
        }

        // 如果缓存中没有，则从数据库获取
        TimbreEntity entity = baseDao.selectById(timbreId);
        if (entity == null) {
            return null;
        }

        // 转换为VO对象
        TimbreDetailsVO details = ConvertUtils.sourceToTarget(entity, TimbreDetailsVO.class);

        // 存入Redis缓存
        if (details != null) {
            redisUtils.set(key, details);
        }

        return details;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void save(TimbreDataDTO dto) {
        isTtsModelId(dto.getTtsModelId());
        TimbreEntity timbreEntity = ConvertUtils.sourceToTarget(dto, TimbreEntity.class);
        baseDao.insert(timbreEntity);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void update(String timbreId, TimbreDataDTO dto) {
        isTtsModelId(dto.getTtsModelId());
        TimbreEntity timbreEntity = ConvertUtils.sourceToTarget(dto, TimbreEntity.class);
        timbreEntity.setId(timbreId);
        baseDao.updateById(timbreEntity);
        // 删除缓存
        redisUtils.delete(RedisKeys.getTimbreDetailsKey(timbreId));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void delete(String[] ids) {
        baseDao.deleteByIds(Arrays.asList(ids));
    }

    @Override
    public List<VoiceDTO> getVoiceNames(String ttsModelId, String voiceName) {
        QueryWrapper<TimbreEntity> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("tts_model_id", StringUtils.isBlank(ttsModelId) ? "" : ttsModelId);
        if (StringUtils.isNotBlank(voiceName)) {
            queryWrapper.like("name", voiceName);
        }
        List<TimbreEntity> timbreEntities = Optional.ofNullable(timbreDao.selectList(queryWrapper)).orElseGet(ArrayList::new);
        List<VoiceDTO> voiceDTOs = timbreEntities.stream()
                .map(entity -> {
                    VoiceDTO dto = new VoiceDTO(entity.getId(), entity.getName());
                    dto.setVoiceDemo(entity.getVoiceDemo());
                    dto.setLanguages(entity.getLanguages()); // 设置语言类型
                    dto.setIsClone(false); // 设置为普通音色
                    return dto;
                })
                .collect(Collectors.toList());

        // 获取当前登录用户ID
        Long currentUserId = SecurityUser.getUser().getId();
        if (currentUserId != null) {
            // 查询用户的所有克隆音色记录
            List<VoiceDTO> cloneEntities = voiceCloneDao.getTrainSuccess(ttsModelId, currentUserId);
            for (VoiceDTO entity : cloneEntities) {
                // 只添加训练成功的克隆音色，且模型ID匹配
                VoiceDTO voiceDTO = new VoiceDTO();
                voiceDTO.setId(entity.getId());
                voiceDTO.setName(MessageUtils.getMessage(ErrorCode.VOICE_CLONE_PREFIX) + entity.getName());
                // 保留从数据库查询到的voiceDemo字段
                voiceDTO.setVoiceDemo(entity.getVoiceDemo());
                voiceDTO.setLanguages(entity.getLanguages());
                voiceDTO.setIsClone(true); // 设置为克隆音色
                redisUtils.set(RedisKeys.getTimbreNameById(voiceDTO.getId()), voiceDTO.getName(),
                        RedisUtils.NOT_EXPIRE);
                voiceDTOs.add(0, voiceDTO);
            }
        }

        return CollectionUtil.isEmpty(voiceDTOs) ? null : voiceDTOs;
    }

    @Override
    public String getDefaultLanguageById(String id) {
        if (StringUtils.isBlank(id)) {
            return null;
        }

        TimbreEntity timbre = timbreDao.selectById(id);
        if (timbre != null) {
            return firstNonBlankLanguage(timbre.getLanguages());
        }

        VoiceCloneEntity voiceClone = voiceCloneDao.selectById(id);
        return voiceClone == null ? null : firstNonBlankLanguage(voiceClone.getLanguages());
    }

    private String firstNonBlankLanguage(String languages) {
        if (StringUtils.isBlank(languages)) {
            return null;
        }
        return LANGUAGE_SEPARATOR.splitAsStream(languages)
                .map(StringUtils::trimToNull)
                .filter(Objects::nonNull)
                .findFirst()
                .orElse(null);
    }

    /**
     * 处理是不是tts模型的id
     */
    private void isTtsModelId(String ttsModelId) {
        // 等模型配置那边写好调用方法判断
    }

    @Override
    public String getTimbreNameById(String id) {
        if (StringUtils.isBlank(id)) {
            return null;
        }

        String cachedName = (String) redisUtils.get(RedisKeys.getTimbreNameById(id));

        if (StringUtils.isNotBlank(cachedName)) {
            return cachedName;
        }

        TimbreEntity entity = timbreDao.selectById(id);
        if (entity != null) {
            String name = entity.getName();
            if (StringUtils.isNotBlank(name)) {
                redisUtils.set(RedisKeys.getTimbreNameById(id), name);
            }
            return name;
        } else {
            VoiceCloneEntity cloneEntity = voiceCloneDao.selectById(id);
            if (cloneEntity != null) {
                String name = MessageUtils.getMessage(ErrorCode.VOICE_CLONE_PREFIX) + cloneEntity.getName();
                redisUtils.set(RedisKeys.getTimbreNameById(id), name);
                return name;
            }
        }

        return null;
    }

    @Override
    public VoiceDTO getByVoiceCode(String ttsModelId, String voiceCode) {
        if (StringUtils.isBlank(voiceCode)) {
            return null;
        }
        QueryWrapper<TimbreEntity> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("tts_model_id", ttsModelId);
        queryWrapper.eq("tts_voice", voiceCode);
        List<TimbreEntity> list = timbreDao.selectList(queryWrapper);
        if (list.isEmpty()) {
            return null;
        }
        TimbreEntity entity = list.get(0);
        VoiceDTO dto = new VoiceDTO(entity.getId(), entity.getName());
        dto.setVoiceDemo(entity.getVoiceDemo());
        dto.setIsClone(false); // 设置为普通音色
        return dto;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int importHuoshanVoices(String ttsModelId) {
        String targetModelId = StringUtils.isNotBlank(ttsModelId) ? ttsModelId : "TTS_HuoshanDoubleStreamTTS";

        // 火山引擎 / 豆包官方全系列音色结构化元数据
        String[][] presets = {
            // 通用 / 日常 / 陪伴推荐系列
            {"zh_female_wanwanxiaohe_moon_bigtts", "湾湾小何", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%B9%BE%E6%B9%BE%E5%B0%8F%E4%BD%95.mp3", "台湾口音（台普），自然亲切温柔聊天陪伴"},
            {"zh_female_shuangkuaisisi_moon_bigtts", "爽快思思/Skye", "中文、英文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/Skye.mp3", "通用女声，爽快开朗有活力"},
            {"zh_male_wennuanahu_moon_bigtts", "温暖阿虎/Alvin", "中文、英文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/Alvin.mp3", "温暖治愈男声，贴心伴侣"},
            {"zh_male_shaonianzixin_moon_bigtts", "少年梓辛/Brayan", "中文、英文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/Brayan.mp3", "阳光少年音，青春朝气"},
            {"zh_female_linjianvhai_moon_bigtts", "邻家女孩", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E9%82%BB%E5%AE%B6%E5%A5%B3%E5%AD%A9.mp3", "邻家软萌女声，清纯甜美"},
            {"zh_male_yuanboxiaoshu_moon_bigtts", "渊博小叔", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%B8%8A%E5%8D%9A%E5%B0%8F%E5%8F%94.mp3", "成熟稳重磁性男声，知识型伴侣"},
            {"zh_male_yangguangqingnian_moon_bigtts", "阳光青年", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E9%98%B3%E5%85%89%E9%9D%92%E5%B9%B4.mp3", "活力青年男声，元气满满"},
            {"zh_male_jingqiangkanye_moon_bigtts", "京腔侃爷/Harmony", "中文、英文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/Harmony.mp3", "风趣幽默京味男声"},
            {"zh_female_cancan_mars_bigtts", "灿灿/Shiny", "中文、英文", null, "知性温婉，支持中英双语"},
            {"zh_female_qingxinnvsheng_mars_bigtts", "清新女声", "中文", null, "清新淡雅，舒适耐听"},
            {"zh_female_zhixingnvsheng_mars_bigtts", "知性女声", "中文", null, "知性优雅，专业沉稳"},
            {"zh_male_qingshuangnanda_mars_bigtts", "清爽男大", "中文", null, "大学阳光学长男声"},
            {"zh_male_wenrouxiaoge_mars_bigtts", "温柔小哥", "中文", null, "细腻柔和暖心男声"},
            {"zh_female_tianmeixiaoyuan_moon_bigtts", "甜美小源", "中文", null, "甜美活泼少女声"},
            {"zh_female_qingchezizi_moon_bigtts", "清澈梓梓", "中文", null, "清澈纯净，灵动悦耳"},
            {"zh_male_jieshuoxiaoming_moon_bigtts", "解说小明", "中文", null, "沉浸解说风，富有感染力"},
            {"zh_female_kailangjiejie_moon_bigtts", "开朗姐姐", "中文", null, "大方从容开朗大姐姐"},
            {"zh_male_linjiananhai_moon_bigtts", "邻家男孩", "中文", null, "亲切随和少年邻家音"},
            {"zh_female_tianmeiyueyue_moon_bigtts", "甜美悦悦", "中文", null, "甜美女友，软萌温柔"},
            {"zh_female_xinlingjitang_moon_bigtts", "心灵鸡汤", "中文", null, "温暖治愈，倾听陪伴"},

            // 特色方言系列
            {"zh_female_daimengchuanmei_moon_bigtts", "呆萌川妹", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E5%91%86%E8%90%8C%E5%B7%9D%E5%A6%B9.mp3", "地道四川方言，古灵精怪"},
            {"zh_male_guozhoudege_moon_bigtts", "广州德哥", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E5%B9%BF%E5%B7%9E%E5%BE%B7%E5%93%A5.mp3", "地道广普/粤语风味，幽默接地气"},
            {"zh_male_beijingxiaoye_moon_bigtts", "北京小爷", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E5%8C%97%E4%BA%AC%E5%B0%8F%E7%88%B7.mp3", "老北京胡同口音，随性侃大山"},
            {"zh_male_haoyuxiaoge_moon_bigtts", "浩宇小哥", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%B5%A9%E5%AE%87%E5%B0%8F%E5%93%A5.mp3", "东北幽默热情小哥，直爽有趣"},
            {"zh_male_guangxiyuanzhou_moon_bigtts", "广西远舟", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E5%B9%BF%E8%A5%BF%E8%BF%9C%E8%88%9F.mp3", "广西风味普通话，质朴亲切"},
            {"zh_female_meituojieer_moon_bigtts", "妹坨洁儿", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E5%A6%B9%E5%9D%A8%E6%B4%81%E5%84%BF.mp3", "湖南湘味小妹，火辣灵动"},
            {"zh_male_yuzhouzixuan_moon_bigtts", "豫州子轩", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E8%B1%AB%E5%B7%9E%E5%AD%90%E8%BD%A9.mp3", "河南中原醇厚乡音"},
            {"zh_female_wanqudashu_moon_bigtts", "湾区大叔", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%B9%BE%E5%8C%BA%E5%A4%A7%E5%8F%94.mp3", "粤港澳湾区成熟大叔风"},

            // 角色扮演与情感系列
            {"zh_female_gaolengyujie_moon_bigtts", "高冷御姐", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E9%AB%98%E5%86%B7%E5%BE%A1%E5%A7%90.mp3", "气场强大高冷御姐音"},
            {"zh_male_aojiaobazong_moon_bigtts", "傲娇霸总", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E5%82%B2%E5%A8%87%E9%9C%B8%E6%80%BB.mp3", "霸道总裁傲娇宠溺男声"},
            {"zh_female_meilinvyou_moon_bigtts", "魅力女友", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E9%AD%85%E5%8A%9B%E5%A5%B3%E5%8F%8B.mp3", "温柔迷人魅力女友音"},
            {"zh_male_shenyeboke_moon_bigtts", "深夜播客", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%B7%B1%E5%A4%9C%E6%92%AD%E5%AE%A2.mp3", "深夜情感电台男主播，磁性治愈"},
            {"zh_female_sajiaonvyou_moon_bigtts", "柔美女友", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%9F%94%E7%BE%8E%E5%A5%B3%E5%8F%8B.mp3", "小鸟依人柔美女友音"},
            {"zh_female_yuanqinvyou_moon_bigtts", "撒娇学妹", "中文", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%92%92%E5%A8%87%E5%AD%A6%E5%A6%B9.mp3", "可爱调皮撒娇小师妹"},
            {"zh_female_shuangkuaisisi_emo_v2_mars_bigtts", "爽快思思(多情感版)", "中文", null, "支持开心、悲伤、激动等多情感渲染"},

            // 豆包 2.0 大模型音色系列 (Uranus)
            {"zh_female_xiaohe_uranus_bigtts", "小何 2.0 (豆包旗舰)", "中文", null, "豆包 2.0 大模型旗舰女声，极其自然拟人"},
            {"zh_female_shuangkuaisisi_uranus_bigtts", "爽快思思 2.0", "中文", null, "豆包 2.0 大模型女声，爽快活力"},
            {"zh_male_m191_uranus_bigtts", "云舟 2.0", "中文", null, "豆包 2.0 大模型旗舰男声，沉稳大气"},
            {"zh_male_taocheng_uranus_bigtts", "小天 2.0", "中文", null, "豆包 2.0 青年男声，生动自然"},
            {"zh_male_liufei_uranus_bigtts", "刘飞 2.0", "中文", null, "豆包 2.0 叙事播报男声"},
            {"zh_male_sophie_uranus_bigtts", "魅力苏菲 2.0", "中文", null, "豆包 2.0 魅力磁性男声"},
            {"zh_female_qingxinnvsheng_uranus_bigtts", "清新女声 2.0", "中文", null, "豆包 2.0 清新脱俗女声"},
            {"zh_female_tianmeixiaoyuan_uranus_bigtts", "甜美小源 2.0", "中文", null, "豆包 2.0 灵动甜美女声"},
            {"zh_female_tianmeitaozi_uranus_bigtts", "甜美桃子 2.0", "中文", null, "豆包 2.0 活泼甜美少女音"},
            {"zh_female_liuchangnv_uranus_bigtts", "流畅女声 2.0", "中文", null, "豆包 2.0 有声读物流畅伴读女声"},
            {"zh_female_xiaoxue_uranus_bigtts", "儿童绘本 2.0", "中文", null, "豆包 2.0 亲切童趣绘本讲故事音"},
            {"zh_female_kefunvsheng_uranus_bigtts", "暖阳女声 2.0", "中文", null, "豆包 2.0 温暖亲和客服音"},
            {"zh_female_vv_uranus_bigtts", "Vivi 2.0", "中文、日文、英文", null, "豆包 2.0 多语种拟人女声"},

            // 多语种与外语系列
            {"multi_male_jingqiangkanye_moon_bigtts", "かずね（和音）", "日语、西语", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/Javier.wav", "多语种青年男声，日语/西语"},
            {"multi_female_shuangkuaisisi_moon_bigtts", "はるこ（晴子）", "日语、西语", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/Esmeralda.mp3", "多语种元气女声，日语/西语"},
            {"multi_female_gaolengyujie_moon_bigtts", "あけみ（朱美）", "日语", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/%E6%9C%B1%E7%BE%8E.mp3", "日语音色，冷艳知性御姐"},
            {"multi_male_wanqudashu_moon_bigtts", "ひろし（広志）", "日语、西语", "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/portal/bigtts/Roberto.wav", "日语音色，成熟稳重大叔"},
            {"en_female_dacey_uranus_bigtts", "Dacey 英文 2.0", "英文", null, "纯正美式英语发音女声"}
        };

        int count = 0;
        long baseSort = 1;

        for (String[] p : presets) {
            String voiceCode = p[0];
            String name = p[1];
            String languages = p[2];
            String demo = p[3];
            String remark = p[4];

            QueryWrapper<TimbreEntity> qw = new QueryWrapper<>();
            qw.eq("tts_model_id", targetModelId);
            qw.eq("tts_voice", voiceCode);
            List<TimbreEntity> existing = timbreDao.selectList(qw);

            if (existing != null && !existing.isEmpty()) {
                TimbreEntity entity = existing.get(0);
                entity.setName(name);
                entity.setLanguages(languages);
                if (StringUtils.isNotBlank(demo)) {
                    entity.setVoiceDemo(demo);
                }
                entity.setRemark(remark);
                entity.setSort(baseSort++);
                timbreDao.updateById(entity);
            } else {
                TimbreEntity entity = new TimbreEntity();
                String candidateId = targetModelId + "_" + String.format("%04d", baseSort);
                if (timbreDao.selectById(candidateId) != null) {
                    candidateId = targetModelId + "_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
                }
                entity.setId(candidateId);
                entity.setTtsModelId(targetModelId);
                entity.setTtsVoice(voiceCode);
                entity.setName(name);
                entity.setLanguages(languages);
                entity.setVoiceDemo(demo);
                entity.setRemark(remark);
                entity.setSort(baseSort++);
                timbreDao.insert(entity);
            }
            count++;
        }

        return count;
    }
}
