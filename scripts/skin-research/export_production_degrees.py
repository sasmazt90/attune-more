"""Export only accepted product heads from frozen tensors; no fitting/test read."""
import json,time
import numpy as np,torch,onnxruntime as ort
from torch import nn
from safetensors.torch import load_file
from train_focused_type import setup,model,features,image,OUT,write,sha
from prepare_focused_data import TARGETS

def main():
    _,rows=setup();final=json.loads((OUT/'degrees-final-test.json').read_text());selected=json.loads((OUT/'type-frozen-selection.json').read_text());frozen=json.loads((OUT/'degrees-frozen-selection.json').read_text());original=json.loads((OUT/'degrees-export.json').read_text())
    targets=[h['target'] for h in final['heads'] if h.get('accepted') and h['target'] in ['tone','oil','redness','dry','lines','dark','bags']]
    assert targets and sha(OUT/'degrees-frozen-head.npz')==frozen['headSHA256'] and sha(OUT/'degrees.onnx')==original['sha256']
    name=selected['model'];net=model(name);assert sha(OUT/name/'selected.safetensors')==selected['weightsSHA256'];net.load_state_dict(load_file(str(OUT/name/'selected.safetensors')));net.eval();head=np.load(OUT/'degrees-frozen-head.npz',allow_pickle=False);ids=[TARGETS.index(t) for t in targets]
    class ProductHeads(nn.Module):
        def __init__(self):
            super().__init__();self.backbone=net
            for key,value in [('mean',head['mean']),('std',head['std']),('weights',head['weights'][ids]),('bias',head['bias'][ids])]:self.register_buffer(key,torch.tensor(value,dtype=torch.float32))
        def forward(self,x):return torch.clamp(((features(self.backbone,name,x)-self.mean)/self.std)@self.weights.T+self.bias,0,5)
    product=ProductHeads().eval();path=OUT/'degrees-product.onnx';torch.onnx.export(product,torch.randn(1,3,224,224),str(path),input_names=['rgb'],output_names=['appearance_grades'],opset_version=17,dynamo=False)
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);full=ort.InferenceSession(str(OUT/'degrees.onnx'),sess_options=options,providers=['CPUExecutionProvider']);parity=[]
    for row in [r for r in rows if r['split']=='validation'][:8]:
        x=image(row)[None].numpy();value=session.run(None,{'rgb':x})[0];expected=full.run(None,{'rgb':x})[0][:,ids]
        with torch.inference_mode():reference=product(torch.from_numpy(x)).numpy()
        assert value.shape==(1,len(targets));parity.append(float(max(np.max(np.abs(value-expected)),np.max(np.abs(value-reference)))))
    assert max(parity)<1e-3
    write('degrees-product-export.json',dict(sha256=sha(path),bytes=path.stat().st_size,targets=targets,sourceResearchONNXHash=original['sha256'],frozenHeadSHA256=frozen['headSHA256'],validationOnlyParity=max(parity),noTestInputsRead=True,rejectedHeadWeightsExported=False,input='RGB source camera-crop-v1 -> INTER_AREA224 -> ImageNet normalization'))
    print(targets,sha(path),max(parity),flush=True)

if __name__=='__main__':main()
