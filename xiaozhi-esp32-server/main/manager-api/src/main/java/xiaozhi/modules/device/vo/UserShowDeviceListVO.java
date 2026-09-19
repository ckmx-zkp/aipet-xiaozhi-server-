package xiaozhi.modules.device.vo;

import java.util.Date;

import com.fasterxml.jackson.annotation.JsonFormat;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "用户显示设备列表VO")
public class UserShowDeviceListVO {

    @Schema(description = "app版本")
    private String appVersion;

    @Schema(description = "绑定用户名称")
    private String bindUserName;

    @Schema(description = "设备型号")
    private String deviceType;

    @Schema(description = "设备型号(board)")
    private String board;

    @Schema(description = "设备唯一标识符")
    private String id;

    @Schema(description = "mac地址")
    private String macAddress;

    @Schema(description = "设备别名")
    private String alias;

    @Schema(description = "自动更新开关(0关闭/1开启)")
    private Integer autoUpdate;

    @Schema(description = "绑定智能体ID")
    private String agentId;

    @Schema(description = "绑定智能体名称")
    private String agentName;

    @Schema(description = "设备专属TTS模型ID")
    private String ttsModelId;

    @Schema(description = "设备专属音色ID")
    private String ttsVoiceId;

    @Schema(description = "设备当前生效音色名称")
    private String ttsVoiceName;

    @Schema(description = "设备专属TTS音量")
    private Integer ttsVolume;

    @Schema(description = "设备专属TTS语速")
    private Integer ttsRate;

    @Schema(description = "设备专属TTS音调")
    private Integer ttsPitch;

    @Schema(description = "最近对话时间")
    private String recentChatTime;

    @Schema(description = "最后连接时间戳（毫秒）", type = "string", example = "1783689702000")
    private Long lastConnectedAtTimestamp;

    @Schema(description = "绑定时间戳（毫秒）", type = "string", example = "1783689702000")
    private Long createDateTimestamp;

    @Schema(description = "绑定时间（兼容字段，请使用 createDateTimestamp）", deprecated = true)
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")
    private Date createDate;

}
