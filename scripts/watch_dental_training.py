"""Validation-only early stopping of this task's already running CPU trainer."""
import argparse, hashlib, json, time
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit-results/combined-health-20261008/dental-training'


def decision(history, minimum_epochs=8, patience=3, minimum_improvement=.005):
    significant_best=-1.; waiting=0
    for row in history:
        score=row['validation']['macroF1']
        if score>significant_best+minimum_improvement:
            significant_best=score;waiting=0
        else:waiting+=1
    return len(history)>=minimum_epochs and waiting>=patience


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pid',type=int,required=True);args=parser.parse_args()
    process=psutil.Process(args.pid);command=process.cmdline()
    assert 'scripts/train_dental_yolox.py' in ' '.join(command)
    assert not (OUT/'heldout-predictions.json').exists(), 'Register stopping rule before held-out evaluation'
    config=dict(maximumEpochs=20,minimumCompletedEpochs=8,validationPatience=3,minimumMacroF1Improvement=.005,
                rule='Validation only; retain actual highest-F1 checkpoint/threshold; held-out unused',
                registeredUnixTime=time.time(),trainerPID=args.pid,trainerCommand=command,
                trainingScriptSHA256=hashlib.sha256((ROOT/'scripts/train_dental_yolox.py').read_bytes()).hexdigest())
    (OUT/'early-stopping-config.json').write_text(json.dumps(config,indent=2),'utf8')
    seen=0
    while process.is_running() and process.status()!=psutil.STATUS_ZOMBIE:
        try:history=json.loads((OUT/'training-history.json').read_text('utf8'))
        except (FileNotFoundError,json.JSONDecodeError):history=[]
        if len(history)!=seen:
            seen=len(history);print(json.dumps({'completedEpochs':seen,'validation':history[-1]['validation'] if history else None}),flush=True)
        if len(history)<config['maximumEpochs'] and decision(history):
            assert process.cmdline()==command
            process.suspend()
            # History is written after both complete NPZ checkpoints.
            frozen=json.loads((OUT/'training-history.json').read_text('utf8'))
            assert frozen==history
            import numpy as np
            with np.load(OUT/'best-weights.npz',allow_pickle=False) as checkpoint:
                assert checkpoint.files and all(np.isfinite(checkpoint[key]).all() for key in checkpoint.files)
            proof=dict(**config,completedEpochs=len(history),trainingHistorySHA256=hashlib.sha256((OUT/'training-history.json').read_bytes()).hexdigest(),
                       bestWeightsSHA256=hashlib.sha256((OUT/'best-weights.npz').read_bytes()).hexdigest(),
                       reason='VALIDATION_PLATEAU',heldoutEvaluated=False,partialNextEpochNotSelected=True)
            (OUT/'early-stopping-decision.json').write_text(json.dumps(proof,indent=2),'utf8')
            process.terminate();process.wait(timeout=20)
            print('EARLY_STOP '+json.dumps(proof),flush=True);return
        time.sleep(20)
    print('TRAINER_EXITED_WITHOUT_EARLY_STOP',flush=True)


if __name__=='__main__':main()
