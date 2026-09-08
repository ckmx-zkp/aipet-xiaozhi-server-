import asyncio,json
from core.providers.tools.server_mcp.mcp_client import ServerMCPClient
async def main():
    with open('data/.mcp_server_settings.json') as f:
        config=json.load(f)['mcpServers']['aipet_music_content']
    client=ServerMCPClient(config)
    try:
        await asyncio.wait_for(client.initialize(),30)
        names=[x['function']['name'] for x in client.get_available_tools()]
        assert set(names)=={'search_netease_music','zodiac_fortune','metaphysics_analysis','daily_chat'},names
        print(json.dumps({'xiaozhi_client_connected':client.is_connected(),'tools':names}))
    finally:
        await client.cleanup()
asyncio.run(main())
