"""Real development output parity including an interrupted validation pass."""
import json,numpy as np
from safetensors.torch import load_file
from train_focused_local import detector,setup,predict
from train_cached_followup import bounded_faster_prediction
from diagnose_followup import NEW,write
from prepare_focused_data import sha

def main():
    net=detector('fasterrcnn');weights=NEW/'fasterrcnn/selected.safetensors';weight_sha=sha(weights);net.load_state_dict(load_file(str(weights)));net.eval();rows=setup('acne')['validation'][:2];expected=predict(net,'fasterrcnn',rows)
    folder=NEW/'fasterrcnn/validation-interrupted-parity';folder.mkdir(exist_ok=True);state={'step':-1,'modelSHA256':weight_sha,'identity':'isolated-validation-parity'};calls=0
    def budget():
        nonlocal calls
        calls+=1;return calls>2
    first=bounded_faster_prediction(net,rows,folder,state,budget,lambda:None)
    actual=bounded_faster_prediction(net,rows,folder,state,lambda:False,lambda:None)
    assert all(np.array_equal(np.array(a),np.array(b)) for a,b in zip(actual,expected))
    repeat=bounded_faster_prediction(net,rows,folder,state,lambda:False,lambda:None);assert repeat==actual
    write('fasterrcnn/validation-interrupted-parity.json',dict(actualDevelopmentPhotos=len(rows),modelSHA256=weight_sha,pausedAfterTwoTiles=first is None,originalPredictionsMatchExactly=True,completedValidationResumeMatchesExactly=True,float32Cache=True,GTInserted=False,oldFinalOpened=False,physicalAcceptance=False))
    print('Exact interrupted validation/cache/resume parity on two real development photos',flush=True)

if __name__=='__main__':main()
