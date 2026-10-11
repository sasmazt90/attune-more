"""Native-source frozen RPN coverage and same-sample float16 loss audit."""
import json,torch,numpy as np
from train_focused_local import setup,acne_tiles,tile_image,detector
from train_cached_followup import faster_loss
from torchvision.ops import box_iou
from diagnose_followup import NEW,write

def main():
    torch.set_num_threads(2);net=detector('fasterrcnn');net.eval();result=[];parity=[]
    for split in ['train','validation']:
        tiles=acne_tiles(setup('acne')[split]);positive=[t for t in tiles if t['boxes']];chosen=[positive[int(i)] for i in np.linspace(0,len(positive)-1,8).astype(int)]
        for index,t in enumerate(chosen):
            x=tile_image(t)[[2,1,0]]/255;target={'boxes':torch.tensor(t['boxes'],dtype=torch.float32),'labels':torch.ones(len(t['boxes']),dtype=torch.int64)}
            with torch.no_grad():
                imgs,targets=net.transform([x],[target]);features=net.backbone(imgs.tensors);original_sizes=net.rpn.anchor_generator.sizes;proposals,_=net.rpn(imgs,features);coverage=box_iou(target['boxes'],proposals[0]).max(1).values.numpy()
                anchor_comparison=[]
                for sizes in [(8,16,32,64,128),(4,8,16,32,64)]:
                    net.rpn.anchor_generator.sizes=tuple((size,) for size in sizes)
                    smaller,_=net.rpn(imgs,features);matches=box_iou(target['boxes'],smaller[0]).max(1).values.numpy();anchor_comparison.append(dict(sizes=list(sizes),recallAtIoU50=float((matches>=.5).mean()),maxIoU=matches.tolist()))
                net.rpn.anchor_generator.sizes=original_sizes
                sampled,_,labels,reg=net.roi_heads.select_training_samples(proposals,targets);roi=net.roi_heads.box_head(net.roi_heads.box_roi_pool(features,sampled,imgs.image_sizes))
                file={'features':roi.numpy(),'labels':labels[0].numpy(),'regression':reg[0].numpy()};rounded={k:v.astype(np.float16) if v.dtype.kind=='f' else v for k,v in file.items()};a,_=faster_loss(net,[file],[t]);b,_=faster_loss(net,[rounded],[t]);error=abs(float(a)-float(b));assert error<.02
            sizes=np.array(t['boxes'])[:,2:]-np.array(t['boxes'])[:,:2]
            result.append(dict(split=split,sha256=t['row']['sha256'],rect=t['rect'],groundTruthBoxes=len(t['boxes']),rawRPNProposals=len(proposals[0]),recallAtIoU50=float((coverage>=.5).mean()),originalAnchorSizes=[list(v) for v in original_sizes],smallAnchorDevelopmentComparison=anchor_comparison,minimumSides=sizes.min(1).tolist(),maxIoU=coverage.tolist(),groundTruthInjectedOnlyForTrainingROI=True))
            parity.append(dict(split=split,index=index,exactLoss=float(a),float16RoundtripLoss=float(b),difference=error,sameROISamples=True))
    write('fasterrcnn/frozen-stage-audit.json',dict(samples=result,lossParity=parity,selection='eight evenly spaced positive native tiles per development split',wholeRPNConverged=False,oldFinalOpened=False,productAccepted=False))
    print(json.dumps(dict(RPNRecall=[(s['split'],round(s['recallAtIoU50'],3)) for s in result],maxLossQuantizationError=max(p['difference'] for p in parity))),flush=True)

if __name__=='__main__':main()
