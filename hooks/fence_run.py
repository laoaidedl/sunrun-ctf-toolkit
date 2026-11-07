# -*- coding: utf-8 -*-
"""只读挂载 fence_dump:抓围栏 polygon 顶点。第二个会话(仅dump,风险低)。"""
import frida, sys, time

def on_msg(m, d):
    if m['type'] == 'send':
        p = str(m['payload'])
        print(p[:3000], flush=True)
        if p.startswith('PTS_'):
            with open('fence_pts.log', 'a', encoding='utf-8') as f:
                f.write(p + '\n')
    elif m['type'] == 'error':
        print('[err]', str(m.get('description'))[:200], flush=True)

open('fence_pts.log', 'w').close()
dev = frida.get_device_manager().add_remote_device('127.0.0.1:39571')
session = dev.attach(2496)
script = session.create_script(open('fence_dump.js', encoding='utf-8').read())
script.on('message', on_msg)
script.load()
print('[fence] loaded', flush=True)
time.sleep(600)
