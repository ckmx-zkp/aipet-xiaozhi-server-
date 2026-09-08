'''陪伴工具身份由已认证的设备连接提供，不能由模型参数选择。'''
COMPANION_HINT = '''
【陪伴工具使用约定】
日常聊天调用companion_reply或daily_chat，星座运势调用zodiac_fortune，文化玄学解读调用metaphysics_analysis；必须取得成功的真实联网结果再回答，失败明确告知，不用自己的知识伪装联网。
这些工具已内部读取当前主人、宠物、关系与批准偏好，不必每轮先调用conversation_plan。只需查看沟通策略时才用conversation_plan；需要先检索再讨论时用context_search，随后用完全相同topic和search_id调用companion_reply复用证据，避免重复联网。
搜索topic只包含公开主题，个人细节放context，不将姓名、联系方式、私密记忆拼入公开搜索。
用户明确反馈沟通偏好时用interaction_feedback保存候选，并说明需在App批准；不要声称已经永久记住。希望一起做活动时用shared_activity。
只有用户明确要求或同意跟进才用followup_plan创建约定；先明确时间和时区。仅在到期后的合适会话内关心，不能承诺离线准点提醒。用户说取消或完成时调用工具并核实结果。
只朗读工具content中的最终答案，不朗读内部策略、身份、来源网址或思考过程，不再次改写出无依据的事实。硬件动作只有设备工具成功才可声称完成。
'''
def bind_companion_scope(name, config, conn):
    if name != 'aipet_music_content':
        return config
    result = dict(config)
    headers = {k: v for k, v in config.get('headers', {}).items()
               if not k.lower().startswith('x-companion-')}
    business = conn.config.get('business_api', {})
    headers.update({
        'X-Companion-Device': str(conn.device_id).strip().lower(),
        'X-Companion-Session': str(conn.session_id),
        'X-Companion-Token': business.get('token', ''),
    })
    result['headers'] = headers
    return result
