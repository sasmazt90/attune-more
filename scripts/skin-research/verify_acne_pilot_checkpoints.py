"""Load preserved optimizer/scheduler/RNG states and run focused regressions."""
import importlib.util
import json
import random
import unittest

from acne_takeover_support import ROOT, OUT, read, digest
from heavy_job_lease import HeavyJobLease


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value,list) else value


def main():
    records=[]
    with HeavyJobLease('CDC-acne-checkpoint-and-focused-regressions',peak_mib=1350,minimum_available_mib=1600,memory_metric='private') as lease:
        import numpy as np
        import torch
        from safetensors.torch import load_file
        from yolox_p2 import build_yolox_p2_model
        torch.set_num_threads(4)
        for arm in ('control','hard-negative'):
            lease.check()
            folder=OUT/('clean-pilot-'+arm)
            receipt=read(folder/'receipt.json');pointer=read(folder/'CURRENT');generation=folder/pointer['directory']
            assert generation.resolve().is_relative_to(folder.resolve())
            for name,expected in pointer['hashes'].items():assert digest(generation/name)==expected
            net=build_yolox_p2_model();net.load_state_dict(load_file(str(generation/'model.safetensors')),strict=True)
            params=[p for name,p in net.named_parameters() if name in receipt['onlyTrainableParameters']]
            opt=torch.optim.AdamW(params,lr=3e-5)
            sched=torch.optim.lr_scheduler.LambdaLR(opt,lambda step:1.)
            state=read(generation/'state.json');tensors=load_file(str(generation/'optimizer-rng.safetensors'))
            reconstructed={int(i):{k:tensors[v['tensor']] if isinstance(v,dict) and 'tensor' in v else v for k,v in values.items()} for i,values in state['optimizerState'].items()}
            opt.load_state_dict(dict(state=reconstructed,param_groups=state['paramGroups']))
            sched.load_state_dict(state['scheduler'])
            assert len(opt.state)==len(params)==8 and sched.last_epoch==150 and state['step']==150
            for param,values in opt.state.items():
                assert values['exp_avg'].shape==values['exp_avg_sq'].shape==param.shape
                assert torch.isfinite(values['exp_avg']).all() and torch.isfinite(values['exp_avg_sq']).all()
                assert float(values['step'])==150
            torch.set_rng_state(tensors['torch_rng']);random.setstate(tuples(state['pythonRNG']))
            rng=state['numpyRNG'];np.random.set_state((rng[0],np.array(rng[1],dtype=np.uint32),*rng[2:]))
            assert torch.equal(torch.get_rng_state(),tensors['torch_rng'])
            records.append(dict(arm=arm,step=150,strictModelLoad=True,optimizerTensorShapesVerified=True,schedulerRestored=True,torchPythonNumpyRNGRestored=True,generation=pointer['directory'],modelSHA256=digest(generation/'model.safetensors')))
            del net,opt,sched,tensors,reconstructed
        suite=unittest.TestSuite()
        for filename in ('test_acne_clean_supervision.py','test_acne_staging_support.py','test_acne_object_negative_scope.py'):
            spec=importlib.util.spec_from_file_location(filename[:-3],ROOT/'tests/unit'/filename);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        assert result.wasSuccessful()
        payload=dict(checkpoints=records,pythonTests=result.testsRun,failures=len(result.failures),errors=len(result.errors),resource=lease.receipt())
    (OUT/'focused-verification.json').write_text(json.dumps(payload,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in payload.items() if k!='resource'}))


if __name__=='__main__':main()
