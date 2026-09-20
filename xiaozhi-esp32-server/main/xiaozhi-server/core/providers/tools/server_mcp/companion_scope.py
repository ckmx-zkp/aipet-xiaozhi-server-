'''陪伴工具身份由已认证的设备连接提供，不能由模型参数选择。'''
COMPANION_HINT = '''
【陪伴工具使用约定】
讲故事、说笑话、陪聊请直接用自己的话完成，不要调用daily_chat、companion_reply或shared_activity。娱乐内容允许不联网。
星座运势调用zodiac_fortune，文化玄学解读调用metaphysics_analysis；必须取得成功的真实联网结果再回答，失败明确告知，不用自己的知识伪装联网。
若误调用了日常聊天、故事或笑话工具且返回失败，立即用自己的话讲完，不要说素材失败或让用户稍候。
这些工具已内部读取当前主人、宠物、关系与批准偏好，不必每轮先调用conversation_plan。只需查看沟通策略时才用conversation_plan；需要先检索公开事实再讨论时用context_search，随后用完全相同topic和search_id调用companion_reply复用证据。
搜索topic只包含公开主题，个人细节放context，不将姓名、联系方式、私密记忆拼入公开搜索。
用户明确反馈沟通偏好时用interaction_feedback保存候选，并说明需在App批准；不要声称已经永久记住。单纯讲故事或说笑话不要调用shared_activity。
只有用户明确要求或同意跟进才用followup_plan创建约定；先明确时间和时区。仅在到期后的合适会话内关心，不能承诺离线准点提醒。用户说取消或完成时调用工具并核实结果。
只朗读工具content中的最终答案，不朗读内部策略、身份、来源网址或思考过程。娱乐工具失败后改口自己讲时除外。硬件动作只有设备工具成功才可声称完成。
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
