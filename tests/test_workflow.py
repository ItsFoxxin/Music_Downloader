import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Store
from app.files import audit, contained, digest, import_files, relative_parts, validate
from app.main import create_app
from app.worker import Worker


@pytest.fixture
def settings(tmp_path):
    s = Settings(config=tmp_path/'config', staging=tmp_path/'staging', media=tmp_path/'media',
                 token='test-token-with-at-least-24-characters', settle_seconds=0,
                 ffprobe=os.getenv('FFPROBE_PATH','ffprobe'), ffmpeg=os.getenv('FFMPEG_PATH','ffmpeg'))
    s.prepare()
    return s


@pytest.fixture
def movie(settings):
    if not shutil.which(settings.ffmpeg) or not shutil.which(settings.ffprobe):
        pytest.fail('Real FFmpeg/ffprobe are required for workflow tests; set FFMPEG_PATH and FFPROBE_PATH.')
    path = settings.staging / '달빛 여행 (2026)' / '달빛 여행.mp4'
    path.parent.mkdir()
    subprocess.run([settings.ffmpeg, '-v','error','-f','lavfi','-i','color=c=blue:s=64x48:r=10',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','0.3','-c:v','mpeg4','-c:a','aac',str(path)],check=True)
    return path


def review(settings, movie):
    store = Store(settings.config/'test.db')
    job = store.enqueue('validate', {'source':movie.parent.name})
    assert Worker(settings, store, None).run_one()
    row = store.job(job['id'])
    assert row['status']=='succeeded', row['error']
    return store, row


def approve(store, row, name='달빛 여행 (2026)'):
    return store.enqueue('import', {'validation_id':row['id'], 'category':'Movies','name':name})


def test_real_decode_import_and_audit(settings,movie):
    source_hash=digest(movie)
    store,row=review(settings,movie)
    assert row['result']['files'][0]['media']['validation']=='full decode'
    job=approve(store,row)
    Worker(settings,store,None).run_one()
    assert store.job(job['id'])['status']=='succeeded'
    assert digest(movie)==source_hash
    copied=settings.media/'Movies'/'달빛 여행 (2026)'/movie.name
    assert digest(copied)==source_hash
    assert not list((settings.media/'.imports').iterdir())
    result=audit(settings,store,job['id'])
    assert result['issues']==[]
    copied.write_bytes(b'corrupted')
    assert audit(settings,store,job['id'])['issues']
    assert store.imports()[0]['health']=='issues found'


def test_changed_source_never_publishes(settings,movie):
    store,row=review(settings,movie)
    movie.write_bytes(b'changed')
    job=approve(store,row)
    Worker(settings,store,None).run_one()
    assert store.job(job['id'])['status']=='failed'
    assert not (settings.media/'Movies'/'달빛 여행 (2026)').exists()
    assert not list((settings.media/'.imports').iterdir())


def test_destination_conflict_preserves_existing(settings,movie):
    store,row=review(settings,movie)
    destination=settings.media/'Movies'/'existing'
    destination.mkdir(parents=True)
    (destination/'keep.txt').write_text('keep')
    job=approve(store,row,'existing')
    Worker(settings,store,None).run_one()
    assert store.job(job['id'])['status']=='failed'
    assert (destination/'keep.txt').read_text()=='keep'
    assert len(list(destination.iterdir()))==1


def test_copy_failure_cleans_only_unpublished_work(settings,movie,monkeypatch):
    store,row=review(settings,movie)
    def fail(*args,**kwargs): raise OSError('simulated disk failure')
    monkeypatch.setattr('app.files.shutil.copyfileobj',fail)
    job=approve(store,row)
    Worker(settings,store,None).run_one()
    assert store.job(job['id'])['status']=='failed'
    assert not list((settings.media/'.imports').iterdir())
    assert movie.exists()


def test_changed_copy_hash_never_publishes(settings,movie,monkeypatch):
    store,row=review(settings,movie)
    monkeypatch.setattr('app.files.digest',lambda p:'wrong')
    job=approve(store,row)
    Worker(settings,store,None).run_one()
    assert store.job(job['id'])['status']=='failed'
    assert not (settings.media/'Movies').exists()


def test_unsupported_files_excluded_and_reported(settings,movie):
    (movie.parent/'installer.exe').write_bytes(b'not executed')
    (movie.parent/'archive.zip').write_bytes(b'not extracted')
    result=validate(settings,None,{'source':movie.parent.name})
    assert len(result['files'])==1
    assert len(result['skipped'])==2
    assert result['warnings']


def test_malformed_media_fails(settings):
    (settings.staging/'bad.mp4').write_bytes(b'not a movie')
    with pytest.raises(ValueError,match='inspection failed'):
        validate(settings,None,{'source':'bad.mp4'})


@pytest.mark.parametrize('path',['../escape','/absolute','a/../../b','C:/windows','a\\b','a//b','a/./b','file:stream','CON','a.','a/'])
def test_unsafe_paths_rejected(settings,path):
    with pytest.raises(ValueError): contained(settings.staging,path,existing=False)


def test_symlink_refused(settings,tmp_path):
    outside=tmp_path/'secret.mp4';outside.write_bytes(b'secret')
    try: (settings.staging/'link.mp4').symlink_to(outside)
    except OSError: pytest.skip('OS does not grant symlink creation to this account')
    with pytest.raises(ValueError,match='Symlinks'):
        contained(settings.staging,'link.mp4')


def test_path_overlap_refused(tmp_path):
    s=Settings(config=tmp_path/'config',staging=tmp_path/'media'/'staging',media=tmp_path/'media',token='x'*32)
    with pytest.raises(ValueError,match='non-overlapping'):s.prepare()


def test_restart_marks_running_job_interrupted(settings):
    store=Store(settings.config/'restart.db')
    job=store.enqueue('validate',{'source':'gone.mp4'})
    store.claim()
    reopened=Store(settings.config/'restart.db')
    assert reopened.job(job['id'])['status']=='interrupted'


def test_receipt_recovers_publish_before_database_failure(settings,movie,monkeypatch):
    store,row=review(settings,movie)
    job=approve(store,row)
    original=store.record_import
    monkeypatch.setattr(store,'record_import',lambda *args: (_ for _ in ()).throw(OSError('DB unavailable')))
    with pytest.raises(OSError):import_files(settings,store,None,job['payload'],job['id'])
    monkeypatch.setattr(store,'record_import',original)
    with store.connect() as c:c.execute("UPDATE jobs SET status='interrupted' WHERE id=?",(job['id'],))
    Worker(settings,store,None).recover()
    assert store.job(job['id'])['status']=='succeeded'
    assert len(store.imports())==1


def test_api_auth_review_import_and_background_results(settings,movie):
    app=create_app(settings,start_worker=False)
    headers={'Authorization':'Bearer '+settings.token}
    with TestClient(app) as client:
        assert client.get('/').status_code==200
        assert client.get('/api/status').status_code==401
        assert client.post('/api/validate',json={'source':movie.parent.name}).status_code==401
        assert client.get('/api/status',headers=headers).status_code==200
        assert 'qbit_password' not in client.get('/api/status',headers=headers).text
        assert client.post('/api/import',headers=headers,json={'validation_id':'a'*32,'category':'Movies','name':'No review'}).status_code==400
        queued=client.post('/api/validate',headers=headers,json={'source':movie.parent.name})
        assert queued.status_code==202
        app.state.worker.run_one()
        job=client.post('/api/import',headers=headers,json={'validation_id':queued.json()['id'],'category':'TV','name':'Show/Season 01'})
        assert job.status_code==202
        app.state.worker.run_one()
        assert app.state.store.job(job.json()['id'])['status']=='succeeded'
        assert len(client.get('/api/library',headers=headers).json())==1
        assert client.post('/api/validate',headers=headers,json={'source':'../outside'}).status_code==400


def test_torrent_incomplete_source_blocks_import(settings,movie):
    class Incomplete:
        def manifest(self,h):raise ValueError('Torrent has not completed downloading.')
    with pytest.raises(ValueError,match='not completed'):
        validate(settings,Incomplete(),{'torrent_hash':'a'*40})


def test_size_mismatch_blocks_validation(settings,movie):
    class WrongSize:
        def manifest(self,h):return [{'path':movie.relative_to(settings.staging).as_posix(),'size':1}]
    with pytest.raises(ValueError,match='size differs'):
        validate(settings,WrongSize(),{'torrent_hash':'a'*40})


def test_completed_torrent_pipeline(settings,movie):
    class Complete:
        def manifest(self,h):return [{'path':movie.relative_to(settings.staging).as_posix(),'size':movie.stat().st_size}]
    store=Store(settings.config/'complete.db')
    job=store.enqueue('validate',{'torrent_hash':'b'*40})
    worker=Worker(settings,store,Complete());worker.run_one()
    assert store.job(job['id'])['status']=='succeeded'
    imported=approve(store,store.job(job['id']))
    worker.run_one()
    assert store.job(imported['id'])['status']=='succeeded'


def test_shared_session_logout_and_csrf(settings):
    with TestClient(create_app(settings,start_worker=False)) as client:
        assert client.get('/api/session').status_code==401
        response=client.post('/api/session',headers={'Authorization':'Bearer '+settings.token})
        assert response.status_code==200
        assert 'HttpOnly' in response.headers['set-cookie']
        assert client.get('/api/session').status_code==200
        assert client.get('/api/status').status_code==200
        assert client.post('/api/logout').status_code==403
        assert client.post('/api/logout',headers={'X-Foxden-Request':'1'}).status_code==200
        assert client.get('/api/session').status_code==401


def test_tampered_session_refused(settings):
    with TestClient(create_app(settings,start_worker=False)) as client:
        client.cookies.set('foxden_session','12345.fake.signature')
        assert client.get('/api/status').status_code==401
