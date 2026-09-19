package xiaozhi.modules.device.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.io.Serializable;

/**
 * 设备更新DTO
 */
@Data
public class DeviceUpdateDTO implements Serializable {
    /**
    * 自动更新状态
    */
    @Max(1)
    @Min(0)
    private Integer autoUpdate;

    /**
    * 设备别名
    */
    @Size(max = 64)
    private String alias;

    /**
    * 绑定智能体ID
    */
    private String agentId;

    /**
    * 设备专属TTS模型ID（传空字符串或null表示跟随智能体）
    */
    private String ttsModelId;

    /**
    * 设备专属音色ID（传空字符串或null表示跟随智能体）
    */
    private String ttsVoiceId;

    /**
    * 设备专属TTS音量
    */
    private Integer ttsVolume;

    /**
    * 设备专属TTS语速
    */
    private Integer ttsRate;

    /**
    * 设备专属TTS音调
    */
    private Integer ttsPitch;

    private static final long serialVersionUID = 1L;
}
