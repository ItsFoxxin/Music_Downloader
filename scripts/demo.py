"""Local-only sample workspace. No real downloads, VPN, NAS, or external torrent calls."""
from pathlib import Path
import argparse
import os
import secrets
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.db import Store
from app.main import create_app
from app.worker import Worker


class DemoQbit:
    def __init__(self, s):
        self.s = s
        self.rows = [
            {'hash':'a'*40,'name':'Moonlit Signals (2026)','progress':1,'amount_left':0,'state':'stalledUP','size':1802000000,'dlspeed':0,'upspeed':45200,'category':'movies','ratio':1.42},
            {'hash':'b'*40,'name':'A Quiet Planet - S01E01','progress':.64,'amount_left':140000000,'state':'downloading','size':720000000,'dlspeed':8240000,'upspeed':203000,'category':'tv','ratio':.2},
            {'hash':'c'*40,'name':'Little Forest - Season 01','progress':.28,'amount_left':110000000,'state':'downloading','size':980000000,'dlspeed':2170000,'upspeed':61000,'category':'tv','ratio':.08},
        ]
    def torrents(self): return self.rows
    def manifest(self,h):
        if h != 'a'*40: raise ValueError('This sample torrent is incomplete.')
        p=self.s.staging/'Moonlit Signals (2026)'/'Moonlit Signals.mp4'
        return [{'path':p.relative_to(self.s.staging).as_posix(),'size':p.stat().st_size}]
    def action(self,h,a):
        row=next(r for r in self.rows if r['hash']==h)
        if a=='stop': row['state']='stoppedUP' if row['progress']==1 else 'stoppedDL'
        elif a=='start': row['state']='stalledUP' if row['progress']==1 else 'downloading'
    def add(self,*args): raise ValueError('Demo mode does not submit real torrents.')


def build(data_dir, token):
    s=Settings(config=data_dir/'config',staging=data_dir/'staging',media=data_dir/'media',token=token,demo=True,settle_seconds=0,
               qbit_url='http://demo.invalid',qbit_public_url='',ffprobe=os.getenv('FFPROBE_PATH','ffprobe'),ffmpeg=os.getenv('FFMPEG_PATH','ffmpeg'))
    s.prepare()
    for folder,filename in [('Moonlit Signals (2026)','Moonlit Signals.mp4'),('A Quiet Planet - S01E01','A Quiet Planet S01E01.mp4')]:
        p=s.staging/folder/filename
        p.parent.mkdir(exist_ok=True)
        if not p.exists():
            subprocess.run([s.ffmpeg,'-v','error','-f','lavfi','-i','color=c=0x88aa77:s=160x90:r=10','-f','lavfi','-i','sine=frequency=330:sample_rate=44100','-t','1','-c:v','mpeg4','-c:a','aac',str(p)],check=True)
    q=DemoQbit(s)
    db=Store(s.config/'media.db')
    if not db.jobs():
        db.enqueue('validate',{'torrent_hash':'a'*40})
        Worker(s,db,q).run_one()
    return create_app(s,qbit=q)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,default=Path('data/demo'))
    parser.add_argument('--port',type=int,default=8010)
    args=parser.parse_args()
    token=os.getenv('APP_TOKEN') or secrets.token_urlsafe(32)
    print('Local demo access token:',token,flush=True)
    print(f'Open http://127.0.0.1:{args.port}',flush=True)
    import uvicorn
    uvicorn.run(build(args.data.absolute(),token),host='127.0.0.1',port=args.port)
