"""TRAIN object-category negatives, never a pixel/healthy-skin annotation.

The source labels a visually reviewed non-Pimple object. Unknown surroundings
remain unknown. Assigned positives and every protected Pimple/pseudo margin win.
"""
def reviewed_object_negative_mask(decoded_cxcywh,negative_xyxy,protected_xyxy):
    import torch
    from torchvision.ops import box_iou
    if not len(negative_xyxy):return torch.zeros((len(decoded_cxcywh),1),dtype=torch.bool,device=decoded_cxcywh.device)
    center=decoded_cxcywh[:,:2];size=decoded_cxcywh[:,2:4];boxes=torch.cat([center-size/2,center+size/2],1)
    neg=negative_xyxy.to(boxes);intersection=(torch.minimum(boxes[:,None,2:],neg[None,:,2:])-torch.maximum(boxes[:,None,:2],neg[None,:,:2])).clamp(min=0).prod(-1)
    area=(boxes[:,2:]-boxes[:,:2]).clamp(min=0).prod(-1).clamp(min=1e-8);neg_area=(neg[:,2:]-neg[:,:2]).clamp(min=0).prod(-1).clamp(min=1e-8)
    inside=((center[:,None]>=neg[None,:,:2])&(center[:,None]<=neg[None,:,2:])).all(-1)
    same_object=(box_iou(boxes,neg)>=.50)|((intersection/area[:,None]>=.90)&inside&(area[:,None]/neg_area[None]>=.25))
    valid=same_object.any(1)
    if len(protected_xyxy):
        protected=protected_xyxy.to(boxes);overlap=(torch.minimum(boxes[:,None,2:],protected[None,:,2:])-torch.maximum(boxes[:,None,:2],protected[None,:,:2])).clamp(min=0).prod(-1);valid &=~(overlap>0).any(1)
    return valid[:,None]
