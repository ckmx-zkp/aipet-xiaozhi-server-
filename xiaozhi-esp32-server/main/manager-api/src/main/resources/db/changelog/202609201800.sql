-- 支持设备独立配置专属音色与语音参数（空值表示继承智能体默认配置）
ALTER TABLE `ai_device` ADD COLUMN `tts_model_id` VARCHAR(64) DEFAULT NULL COMMENT '设备专属TTS模型ID，为空则跟随智能体';
ALTER TABLE `ai_device` ADD COLUMN `tts_voice_id` VARCHAR(64) DEFAULT NULL COMMENT '设备专属音色ID，为空则跟随智能体';
ALTER TABLE `ai_device` ADD COLUMN `tts_volume` INT DEFAULT NULL COMMENT '设备专属TTS音量';
ALTER TABLE `ai_device` ADD COLUMN `tts_rate` INT DEFAULT NULL COMMENT '设备专属TTS语速';
ALTER TABLE `ai_device` ADD COLUMN `tts_pitch` INT DEFAULT NULL COMMENT '设备专属TTS音调';
