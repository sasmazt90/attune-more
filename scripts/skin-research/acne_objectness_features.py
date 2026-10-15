"""Research-only independent objectness features; preserve the original box/class path.

This YOLOX has no obj_convs: obj_preds normally consumes reg_convs output.
Copying those features into an explicit objectness branch allows their learning
without changing the shared stems or the regression/classification functions.
All state must be loaded strictly into this declared graph, never a legacy head.
"""
import copy
import hashlib
import torch

VERSION = 'yolox-p2-independent-objectness-regfeature-copy-v1'


def install_objectness_features(net):
    head = net.head
    if hasattr(head, 'obj_convs'):
        raise ValueError('Objectness feature branch already installed')
    head.obj_convs = copy.deepcopy(head.reg_convs)
    inputs = {}
    handles = []
    for level in range(len(head.stems)):
        def remember(_module, _args, output, level=level):
            if level in inputs:
                raise RuntimeError('Unconsumed objectness stem input')
            inputs[level] = output.detach()
        def replace(_module, args, level=level):
            if len(args) != 1 or level not in inputs:
                raise RuntimeError('Objectness feature forward contract changed')
            return (head.obj_convs[level](inputs.pop(level)),)
        handles.append(head.stems[level].register_forward_hook(remember))
        handles.append(head.obj_preds[level].register_forward_pre_hook(replace))
    # Plain attributes are not model tensor state or persistent photo caches.
    head._objectness_feature_handles = handles
    head._objectness_feature_inputs = inputs
    return net


def configure_learnable(net):
    names = []
    for name, parameter in net.named_parameters():
        selected = name.startswith('head.obj_preds.') or (name.startswith('head.obj_convs.') and '.conv.weight' in name)
        parameter.requires_grad_(selected)
        if selected:
            names.append(name)
    assert len(names) == 16, names
    training_mode(net)
    return names


def training_mode(net):
    net.train()
    for module in net.modules():
        if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
            module.eval()


def frozen_hash(net, trainable_names):
    h = hashlib.sha256()
    for name, tensor in sorted(net.state_dict().items()):
        if name not in trainable_names:
            h.update(name.encode())
            h.update(tensor.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def build_feature_model():
    from yolox_p2 import build_yolox_p2_model
    return install_objectness_features(build_yolox_p2_model())
