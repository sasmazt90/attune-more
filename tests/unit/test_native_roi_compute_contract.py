"""Small-array contracts; no encoder/photo pool, training or browser process."""
import sys,subprocess,types,json,os
from pathlib import Path
import cv2,numpy as np,pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/core-api'));sys.path.insert(0,str(ROOT/'scripts/skin-research'))
import native_flake_support as F,material_component_features as M,heavy_job_lease as H
cv2.setNumThreads(1)

def test_only_ineligible_candidates_are_skipped_with_identical_interest_field():
    rng=np.random.default_rng(31);im=rng.integers(70,140,(80,96,3),dtype=np.uint8);im[25:31,30:37]=200;interest=np.zeros(im.shape[:2],bool);interest[15:45,15:50]=True
    old=types.ModuleType('old');exec(subprocess.check_output(['git','show','ed3cd37:services/core-api/native_flake_support.py'],cwd=ROOT).decode(),old.__dict__)
    before=old.proposal_tile(im,.7);work={};after=F.proposal_tile(im,.7,interest=interest,work=work)
    assert np.array_equal(before[interest],after[interest]) and work['skippedOutsideCoreEligibility']>0

def test_shared_photometry_is_exact_with_original_byte_source():
    rng=np.random.default_rng(12);im=rng.integers(50,220,(80,90,3),dtype=np.uint8);old=F.proposal_tile(im,.8)
    shared=F.proposal_tile(im,.8,photometry=(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),cv2.cvtColor(im,cv2.COLOR_BGR2LAB)[:,:,0]))
    assert np.array_equal(old,shared)

def test_single_crop_excludes_its_foreground_from_ring_reference():
    im=np.full((100,100,3),100,np.uint8);ids=np.zeros((100,100),np.int32);ids[40:46,40:46]=1;im[ids==1]=220;ids[40:46,47:49]=2;im[ids==2]=250;before=im.copy();row={'rect':[40,40,6,6],'componentId':1}
    crop,meta=M.support_conditioned_crop(im,ids,row,1.)
    assert crop.shape==(3,224,224) and meta['ringBGR']==[100,100,100] and not meta['backgroundIncludesCandidate']
    assert np.array_equal(im,before)
    half_im=cv2.resize(im,None,fx=.5,fy=.5);half_ids=cv2.resize(ids.astype(np.float32),None,fx=.5,fy=.5,interpolation=cv2.INTER_NEAREST).astype(np.int32)
    _,half=M.support_conditioned_crop(half_im,half_ids,{'rect':[20,20,3,3],'componentId':1},.5,.5)
    assert meta['width']==half['width']*2 and meta['x']==half['x']*2

def test_atomic_lease_never_removes_foreign_pid_start_job(tmp_path,monkeypatch):
    path=tmp_path/'shared.json';original=json.dumps({'owner':'AG','pid':123,'processStarted':5,'jobId':'foreign'});path.write_text(original)
    monkeypatch.setattr(H,'LOCK',path);monkeypatch.setattr(H,'ag_workers',lambda:[])
    with pytest.raises(H.HeavyJobUnavailable,match='Existing shared lease'):
        with H.HeavyJobLease('CD-test',minimum_available_mib=0):pass
    assert path.read_text()==original

def test_lease_rechecks_pid_start_job_and_only_removes_own_nonce(tmp_path,monkeypatch):
    path=tmp_path/'shared.json';monkeypatch.setattr(H,'LOCK',path);monkeypatch.setattr(H,'ag_workers',lambda:[])
    with H.HeavyJobLease('CD-small-unit',peak_mib=2000,minimum_available_mib=0) as lease:
        row=json.loads(path.read_text());assert row['pid']==os.getpid() and row['jobId']=='CD-small-unit'
        row['nonce']='other';path.write_text(json.dumps(row));lease.last_check=0
        with pytest.raises(H.HeavyJobUnavailable,match='identity'):lease.check()
    assert path.exists()

def test_clipped_proposal_cannot_become_its_own_background_or_healthy_negative():
    im=np.full((60,60,3),100,np.uint8);im[20:40,20:40]=220;field=np.zeros((60,60),np.float32);field[28:31,28:31]=.5
    raw=np.zeros((60,60),bool);raw[20:40,20:40]=True
    with pytest.raises(ValueError,match='INSUFFICIENT_COMPONENT_RING'):M.describe(im,field,1.,reference_support=raw)
    ids=(field>0).astype(np.int32)
    with pytest.raises(ValueError,match='INSUFFICIENT_COMPONENT_RING'):M.support_conditioned_crop(im,ids,dict(rect=[28,28,3,3],componentId=1),1.,reference_support=raw)
