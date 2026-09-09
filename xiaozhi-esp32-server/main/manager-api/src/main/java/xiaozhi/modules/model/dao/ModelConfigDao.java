package xiaozhi.modules.model.dao;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import xiaozhi.common.dao.BaseDao;
import xiaozhi.modules.model.entity.ModelConfigEntity;

@Mapper
public interface ModelConfigDao extends BaseDao<ModelConfigEntity> {

    // 原始 JSON 保留显式 null，供能力探测与乐观更新共用同一快照。
    @org.apache.ibatis.annotations.Select("SELECT model_type AS modelType, CAST(config_json AS CHAR) AS configJsonRaw FROM ai_model_config WHERE id = #{id}")
    Map<String, Object> getValidationSnapshot(@Param("id") String id);

    /**
     * get model_code list
     */
    List<String> getModelCodeList(@Param("modelType") String modelType, @Param("modelName") String modelName);

    /**
     * 获取符合条件的TTS平台列表(id和modelName)
     */
    List<Map<String, Object>> getTtsPlatformList();
}
