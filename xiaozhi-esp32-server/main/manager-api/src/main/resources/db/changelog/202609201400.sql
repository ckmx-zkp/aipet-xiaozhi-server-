-- 接入火山方舟已开通且实测支持视觉的多模态模型清单（2026-09-20）

-- 1. 豆包 Seed 2.0 Mini 视觉模型（低延迟、与主力对话同基底，推荐）
delete from `ai_model_config` where id = 'VLLM_DoubaoSeed20Mini';
INSERT INTO `ai_model_config` (`id`, `model_type`, `model_code`, `model_name`, `is_default`, `is_enabled`, `config_json`, `doc_link`, `remark`, `sort`, `creator`, `create_date`, `updater`, `update_date`, `validity_status`, `validity_reason`, `validity_checked_at`) VALUES 
('VLLM_DoubaoSeed20Mini', 'VLLM', 'openai', '豆包Seed2.0-Mini视觉', 0, 1, '{\"type\": \"openai\", \"model_name\": \"doubao-seed-2-0-mini-260428\", \"base_url\": \"https://ark.cn-beijing.volces.com/api/v3\", \"api_key\": \"YOUR_VOLCENGINE_ARK_API_KEY\"}', 'https://console.volcengine.com/ark/region:cn-beijing/openManagement', '豆包Seed 2.0 Mini视觉模型：低延迟高响应，与主对话模型同款，实测支持图文多模态', 10, 1, NOW(), 1, NOW(), 'valid', '实测图像多模态推理通过', NOW());

-- 2. 豆包 Seed 拟人角色视觉模型
delete from `ai_model_config` where id = 'VLLM_DoubaoSeedCharacter';
INSERT INTO `ai_model_config` (`id`, `model_type`, `model_code`, `model_name`, `is_default`, `is_enabled`, `config_json`, `doc_link`, `remark`, `sort`, `creator`, `create_date`, `updater`, `update_date`, `validity_status`, `validity_reason`, `validity_checked_at`) VALUES 
('VLLM_DoubaoSeedCharacter', 'VLLM', 'openai', '豆包Seed-拟人角色视觉', 0, 1, '{\"type\": \"openai\", \"model_name\": \"doubao-seed-character-260628\", \"base_url\": \"https://ark.cn-beijing.volces.com/api/v3\", \"api_key\": \"YOUR_VOLCENGINE_ARK_API_KEY\"}', 'https://console.volcengine.com/ark/region:cn-beijing/openManagement', '豆包Seed拟人角色视觉模型：具备拟人化角色口吻解读图像能力', 11, 1, NOW(), 1, NOW(), 'valid', '实测图像多模态推理通过', NOW());

-- 3. 豆包 Seed 2.0 Pro 视觉模型
delete from `ai_model_config` where id = 'VLLM_DoubaoSeed20Pro';
INSERT INTO `ai_model_config` (`id`, `model_type`, `model_code`, `model_name`, `is_default`, `is_enabled`, `config_json`, `doc_link`, `remark`, `sort`, `creator`, `create_date`, `updater`, `update_date`, `validity_status`, `validity_reason`, `validity_checked_at`) VALUES 
('VLLM_DoubaoSeed20Pro', 'VLLM', 'openai', '豆包Seed2.0-Pro视觉', 0, 1, '{\"type\": \"openai\", \"model_name\": \"doubao-seed-2-0-pro-260215\", \"base_url\": \"https://ark.cn-beijing.volces.com/api/v3\", \"api_key\": \"YOUR_VOLCENGINE_ARK_API_KEY\"}', 'https://console.volcengine.com/ark/region:cn-beijing/openManagement', '豆包Seed 2.0 Pro高精视觉模型：细节感知力更强，复杂图像分析', 12, 1, NOW(), 1, NOW(), 'valid', '实测图像多模态推理通过', NOW());

-- 4. 豆包 Seed 2.1 Pro 旗舰视觉模型
delete from `ai_model_config` where id = 'VLLM_DoubaoSeed21Pro';
INSERT INTO `ai_model_config` (`id`, `model_type`, `model_code`, `model_name`, `is_default`, `is_enabled`, `config_json`, `doc_link`, `remark`, `sort`, `creator`, `create_date`, `updater`, `update_date`, `validity_status`, `validity_reason`, `validity_checked_at`) VALUES 
('VLLM_DoubaoSeed21Pro', 'VLLM', 'openai', '豆包Seed2.1-Pro旗舰视觉', 0, 1, '{\"type\": \"openai\", \"model_name\": \"doubao-seed-2-1-pro-260915\", \"base_url\": \"https://ark.cn-beijing.volces.com/api/v3\", \"api_key\": \"YOUR_VOLCENGINE_ARK_API_KEY\"}', 'https://console.volcengine.com/ark/region:cn-beijing/openManagement', '豆包Seed 2.1 Pro高阶多模态模型：最新旗舰版高阶图像推理能力', 13, 1, NOW(), 1, NOW(), 'valid', '实测图像多模态推理通过', NOW());

-- 5. 豆包 Seed 2.0 Lite 轻量视觉模型
delete from `ai_model_config` where id = 'VLLM_DoubaoSeed20Lite';
INSERT INTO `ai_model_config` (`id`, `model_type`, `model_code`, `model_name`, `is_default`, `is_enabled`, `config_json`, `doc_link`, `remark`, `sort`, `creator`, `create_date`, `updater`, `update_date`, `validity_status`, `validity_reason`, `validity_checked_at`) VALUES 
('VLLM_DoubaoSeed20Lite', 'VLLM', 'openai', '豆包Seed2.0-Lite视觉', 0, 1, '{\"type\": \"openai\", \"model_name\": \"doubao-seed-2-0-lite-260428\", \"base_url\": \"https://ark.cn-beijing.volces.com/api/v3\", \"api_key\": \"YOUR_VOLCENGINE_ARK_API_KEY\"}', 'https://console.volcengine.com/ark/region:cn-beijing/openManagement', '豆包Seed 2.0 Lite视觉模型：轻量快速视觉处理', 14, 1, NOW(), 1, NOW(), 'valid', '实测图像多模态推理通过', NOW());

-- 6. GLM-5.3-Flash 视觉模型（火山引擎版）
delete from `ai_model_config` where id = 'VLLM_VolcGLM53Flash';
INSERT INTO `ai_model_config` (`id`, `model_type`, `model_code`, `model_name`, `is_default`, `is_enabled`, `config_json`, `doc_link`, `remark`, `sort`, `creator`, `create_date`, `updater`, `update_date`, `validity_status`, `validity_reason`, `validity_checked_at`) VALUES 
('VLLM_VolcGLM53Flash', 'VLLM', 'openai', 'GLM5.3-Flash视觉(火山)', 0, 1, '{\"type\": \"openai\", \"model_name\": \"glm-5-3-flash-260828\", \"base_url\": \"https://ark.cn-beijing.volces.com/api/v3\", \"api_key\": \"YOUR_VOLCENGINE_ARK_API_KEY\"}', 'https://console.volcengine.com/ark/region:cn-beijing/openManagement', 'GLM 5.3 Flash视觉模型（火山部署）：闪电速度多模态视觉响应', 15, 1, NOW(), 1, NOW(), 'valid', '实测图像多模态推理通过', NOW());
