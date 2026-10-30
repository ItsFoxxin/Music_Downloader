import json
import httpx
import pytest
from app.config import Settings
from app.qbit import Qbit


def client(handler):
    q=Qbit(Settings(qbit_url='http://qbit:8080',qbit_download_root='/downloads'))
    q.session=httpx.Client(base_url='http://qbit:8080/',transport=httpx.MockTransport(handler))
    return q


def test_login_cookie_reuse_and_versioned_action():
    paths=[]
    def handle(request):
        paths.append(request.url.path)
        if request.url.path.endswith('/login'):
            return httpx.Response(200,text='Ok.',headers={'set-cookie':'SID=test; Path=/'})
        assert 'SID=test' in request.headers['cookie']
        if request.url.path.endswith('/version'):return httpx.Response(200,text='v4.6.7')
        return httpx.Response(200,text='Ok.')
    q=client(handle);q.action('a'*40,'stop');q.action('a'*40,'start')
    assert paths.count('/api/v2/auth/login')==1
    assert '/api/v2/torrents/pause' in paths and '/api/v2/torrents/resume' in paths


def test_failed_login_is_rate_limited():
    calls=[]
    def handle(r):calls.append(r);return httpx.Response(200,text='Fails.')
    q=client(handle)
    with pytest.raises(ValueError,match='login failed'):q.torrents()
    with pytest.raises(ValueError,match='once per minute'):q.torrents()
    assert len(calls)==1


def test_manifest_mapping_and_skipped_files():
    def handle(r):
        if r.url.path.endswith('/login'):return httpx.Response(200,text='Ok.',headers={'set-cookie':'SID=test; Path=/'})
        if r.url.path.endswith('/info'):return httpx.Response(200,json=[{'hash':'a'*40,'progress':1,'amount_left':0,'state':'stoppedUP','save_path':'/downloads/finished'}])
        return httpx.Response(200,json=[{'name':'Movie/movie.mp4','size':123,'progress':1,'priority':1},{'name':'skip.mp4','size':4,'progress':0,'priority':0}])
    assert client(handle).manifest('a'*40)==[{'path':'finished/Movie/movie.mp4','size':123}]


@pytest.mark.parametrize('change',[{'progress':.5},{'state':'checkingUP'},{'save_path':'/elsewhere'}])
def test_unsafe_torrent_states_refused(change):
    q=Qbit(Settings())
    row={'hash':'a'*40,'progress':1,'amount_left':0,'state':'uploading','save_path':'/downloads'};row.update(change)
    q.torrents=lambda:[row]
    with pytest.raises(ValueError):q.manifest('a'*40)
