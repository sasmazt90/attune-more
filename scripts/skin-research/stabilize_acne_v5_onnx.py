"""Exact logistic representation; avoids ORT Sigmoid negative-tail saturation."""
def stabilize(path):
 import onnx
 g=onnx.load(str(path));nodes=[];count=0
 for node in g.graph.node:
  if node.op_type!='Sigmoid':nodes.append(node);continue
  count+=1;n=f'precise_sigmoid_{count}';one=n+'_one';g.graph.initializer.append(onnx.helper.make_tensor(one,onnx.TensorProto.FLOAT,[],[1.0]))
  nodes.extend([onnx.helper.make_node('Neg',[node.input[0]],[n+'_negative'],name=n+'_neg'),onnx.helper.make_node('Exp',[n+'_negative'],[n+'_exp'],name=n+'_exp'),onnx.helper.make_node('Add',[one,n+'_exp'],[n+'_denominator'],name=n+'_add'),onnx.helper.make_node('Div',[one,n+'_denominator'],list(node.output),name=n+'_div')])
 if not count:return
 del g.graph.node[:];g.graph.node.extend(nodes);onnx.checker.check_model(g);onnx.save(g,str(path))
