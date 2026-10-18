"""Comparable ONNX size/latency/parity of both frozen type candidates.
Validation images only; this script cannot select or reopen a final test.
"""
import json,time
import numpy as np,torch,onnxruntime as ort,psutil
from safetensors.torch import load_file
from train_focused_type import setup,model,image,OUT,write,sha

def main():
    _,rows=setup();val=[r for r in rows if r['split']=='validation'][:8];reports=[]
    for name in ['resnet18','efficientnet_b0']:
        folder=OUT/name;selection=json.loads((folder/'selection.json').read_text());assert sha(folder/'selected.safetensors')==selection['weightsSHA256']
        net=model(name);net.load_state_dict(load_file(str(folder/'selected.safetensors')));net.eval();path=folder/'candidate-export.onnx'
        torch.onnx.export(net,torch.randn(1,3,224,224),str(path),input_names=['rgb'],output_names=['type_logits'],opset_version=17,dynamo=False)
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;rss=psutil.Process().memory_info().rss;start=time.perf_counter();session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider']);cold=(time.perf_counter()-start)*1000
        allocated=psutil.Process().memory_info().rss-rss;timings=[];errors=[]
        for row in val:
            x=image(row)[None].numpy();start=time.perf_counter();actual=session.run(None,{'rgb':x})[0];timings.append((time.perf_counter()-start)*1000)
            with torch.inference_mode():expected=net(torch.from_numpy(x)).numpy()
            errors.append(float(np.max(np.abs(actual-expected))))
        assert max(errors)<1e-3
        reports.append(dict(model=name,weightsSHA256=selection['weightsSHA256'],onnxSHA256=sha(path),modelBytes=path.stat().st_size,coldLoadMs=cold,firstInferenceMs=timings[0],warmInferenceMs=timings[1:],maxAbsParity=max(errors),sessionRSSDelta=allocated,CPUThreads=2,input='RGB native camera-crop-v1 -> INTER_AREA224 -> ImageNet normalization',validationImagesOnly=True))
        del session,net
    write('type-runtime-comparison.json',reports);print(json.dumps(reports,indent=2),flush=True)
if __name__=='__main__':main()
