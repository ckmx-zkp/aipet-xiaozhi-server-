import asyncio,json,urllib.request
from fastmcp import Client
async def main():
    async with Client('http://music-content-mcp:3061/mcp') as c:
        names=[t.name for t in await c.list_tools()]
        print(json.dumps({'tools':names}),flush=True)
        assert len(names)==4
        for name,args in [('search_netease_music',{'song_name':'超能力','artist_name':'邓紫棋'}),('zodiac_fortune',{'zodiac':'处女座'}),('metaphysics_analysis',{'question':'梦见下雨可以怎样理解？'}),('daily_chat',{'topic':'今天工作忙，想放松一下'})]:
            r=await c.call_tool(name,args)
            d=r.data
            if not isinstance(d,dict):
                d=json.loads(r.content[0].text)
            print(json.dumps({'tool':name,'success':d.get('success'),'error_code':d.get('error_code'),'song_id':d.get('song_id'),'characters':len(d.get('content',''))}),flush=True)
            assert d.get('success'), name
            if name=='search_netease_music':
                assert d['song_id']==1833633769
                with urllib.request.urlopen(d['audio_url'],timeout=60) as stream:
                    data=stream.read(8192)
                    assert data.startswith(b'OggS')
                    print(json.dumps({'public_audio_bytes':len(data),'ogg':True}),flush=True)
asyncio.run(main())
