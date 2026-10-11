"""Meaningful local research restart equivalence, not model accuracy claims."""
import json,random,sys
from pathlib import Path
import numpy as np,pytest
torch=pytest.importorskip("torch")
pytest.importorskip("safetensors")
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/skin-research'))
from training_checkpoint import checkpoint,resume

def test_source_padding_impulses_do_not_reject_facial_texture():
    from clean_followup_quality import padding_impulse
    # Deliberate quality geometry unit input, never a camera/user fixture.
    clean=np.full((256,256,3),10,np.uint8);clean[64:192]=[80,110,140]
    # Isolated bright fine details within the photo cannot implicate padding.
    clean[100:150:7,100:150:7]=255
    assert not padding_impulse(clean)['confirmedNumericPattern']
    corrupt=clean.copy()
    for y in [15,25,225,235]:
        for x in [15,25,225,235]:corrupt[y,x]=180
    assert padding_impulse(corrupt)['confirmedNumericPattern']

def test_cached_iou_metrics_preserve_greedy_ties_and_thresholds():
    checkout=ROOT/"audit-results/combined-health-20261008/yolox/extracted/YOLOX-6ddff4824372906469a7fae2dc3206c7aa4bbaee/yolox"
    if not checkout.exists():pytest.skip("Optional licensed research checkout is absent")
    from train_focused_local import detection_metrics as original
    from fast_detection_metrics import detection_metrics as fast
    # Duplicate GT tests the highest-index tuple tie used by the old metric.
    rows=[{'crop':[0,0,100,100],'group':'a','annotations':[{'classId':0,'box':[10,10,20,20]},{'classId':0,'box':[10,10,20,20]},{'classId':0,'box':[60,60,70,70]}]}]
    predictions=[[[10,10,20,20,.8],[11,10,21,20,.7],[30,30,40,40,.4],[60,60,70,70,.2]]]
    for threshold in [.1,.25,.4,.55,.7]:assert fast(rows,predictions,threshold)==original(rows,predictions,threshold)

def test_adamw_rng_cursor_resume_matches_uninterrupted_training(tmp_path):
    torch.manual_seed(82);np.random.seed(82);random.seed(82)
    net=torch.nn.Linear(3,2);opt=torch.optim.AdamW(net.parameters(),lr=.003)
    def step(model,optimizer):
        x=torch.randn(4,3)*np.random.uniform(.8,1.2);y=torch.tensor([random.randrange(2) for _ in range(4)]);optimizer.zero_grad();loss=torch.nn.functional.cross_entropy(model(x),y);loss.backward();optimizer.step()
    step(net,opt);state={'step':1,'identity':'pinned-data','epoch':0,'cursor':4,'order':[4,2,1,0,3]};checkpoint(tmp_path,net,opt,state)
    step(net,opt);expected={k:v.clone() for k,v in net.state_dict().items()};expected_torch=torch.get_rng_state().clone();expected_numpy=np.random.get_state();expected_python=random.getstate()
    restored=torch.nn.Linear(3,2);other=torch.optim.AdamW(restored.parameters(),lr=.4);actual=resume(tmp_path,restored,other,'pinned-data');assert actual['cursor']==4 and actual['order']==state['order']
    # Windows safetensors can hold mapped optimizer sections. A resumed state
    # must support another transaction before the next optimization step.
    checkpoint(tmp_path,restored,other,actual);step(restored,other)
    assert all(torch.equal(v,expected[k]) for k,v in restored.state_dict().items());assert torch.equal(torch.get_rng_state(),expected_torch);assert np.array_equal(np.random.get_state()[1],expected_numpy[1]);assert random.getstate()==expected_python
    with pytest.raises(AssertionError,match='DATA_OR_FREEZE_CHANGED'):resume(tmp_path,restored,other,'different-data')

def test_checkpoint_hash_detects_corrupt_optimizer(tmp_path):
    net=torch.nn.Linear(2,1);opt=torch.optim.AdamW(net.parameters());checkpoint(tmp_path,net,opt,{'step':0,'identity':'x'})
    folder=tmp_path/(tmp_path/'CURRENT').read_text();file=folder/'optimizer.safetensors';file.write_bytes(file.read_bytes()+b'corrupt')
    with pytest.raises(AssertionError):resume(tmp_path,net,opt,'x')
