"""Dataset-independent transactional local optimizer/RNG checkpoints."""
import hashlib,json,random,time
import numpy as np,torch
from safetensors.torch import save_file,load_file

def _sha(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for part in iter(lambda:source.read(1024*1024),b''):value.update(part)
    return value.hexdigest()

def checkpoint(folder,net,opt,state):
    generation=folder/f'checkpoint-{state["step"]:07d}-{time.time_ns():020d}'
    generation.mkdir()
    save_file({k:v.contiguous() for k,v in net.state_dict().items()},str(generation/'model.safetensors'))
    original=opt.state_dict();tensors={'torchRNG':torch.get_rng_state()};scalars={}
    for i,entry in original['state'].items():
        scalars[str(i)]={}
        for key,value in entry.items():
            if torch.is_tensor(value):tensors[f'optimizer.{i}.{key}']=value.contiguous()
            else:scalars[str(i)][key]=value
    save_file(tensors,str(generation/'optimizer.safetensors'))
    state={**state,'optimizerScalars':scalars,'paramGroups':original['param_groups'],'numpyRNG':[np.random.get_state()[0],np.random.get_state()[1].tolist(),*np.random.get_state()[2:]],'pythonRNG':random.getstate()}
    state['modelSHA256']=_sha(generation/'model.safetensors')
    state['optimizerSHA256']=_sha(generation/'optimizer.safetensors')
    (generation/'state.json').write_text(json.dumps(state,indent=2),'utf8')
    pointer=folder/'CURRENT.tmp';pointer.write_text(generation.name,'utf8');pointer.replace(folder/'CURRENT')
    # Persistent training history is never pruned. Time/space limits stop a
    # resumable invocation; they do not authorize deleting earlier checkpoints.
    return state

def resume(folder,net,opt,identity):
    generation=folder/(folder/'CURRENT').read_text('utf8');assert generation.resolve().parent==folder.resolve()
    state=json.loads((generation/'state.json').read_text());assert state['identity']==identity,'DATA_OR_FREEZE_CHANGED'
    assert _sha(generation/'model.safetensors')==state['modelSHA256'] and _sha(generation/'optimizer.safetensors')==state['optimizerSHA256']
    net.load_state_dict(load_file(str(generation/'model.safetensors')));tensors={k:v.clone() for k,v in load_file(str(generation/'optimizer.safetensors')).items()};states={int(i):dict(v) for i,v in state['optimizerScalars'].items()}
    for key,value in tensors.items():
        if key.startswith('optimizer.'):
            _,i,k=key.split('.');states[int(i)][k]=value
    opt.load_state_dict({'state':states,'param_groups':state['paramGroups']});torch.set_rng_state(tensors['torchRNG'])
    n=state['numpyRNG'];np.random.set_state((n[0],np.array(n[1],np.uint32),*n[2:]))
    def tuples(x):return tuple(tuples(v) for v in x) if isinstance(x,list) else x
    random.setstate(tuples(state['pythonRNG']));return state
