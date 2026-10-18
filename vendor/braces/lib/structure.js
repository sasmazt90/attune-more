'use strict';

// Attune local mitigation. Not an upstream fixed version. See LOCAL-PATCH.md.
// Depth counts actual traversed edges, not a caller-supplied AST depth field.
const MAX_DEPTH = 256;
const reject = reason => {
  const error = new RangeError(`braces: unsafe structure (${reason}; maximum depth ${MAX_DEPTH})`);
  error.code = 'ERR_BRACES_STRUCTURE';
  throw error;
};

const nesting = depth => {
  if (depth >= MAX_DEPTH) reject('nesting');
};

// Only traversal edges are followed. Parsed parent/prev backreferences are valid.
const array = value => {
  if (!Array.isArray(value)) return;
  const active = new WeakSet();
  const stack = [{ value, index: 0 }];
  active.add(value);
  while (stack.length) {
    const frame = stack[stack.length - 1];
    if (frame.index === frame.value.length) {
      active.delete(frame.value); stack.pop(); continue;
    }
    const child = frame.value[frame.index++];
    if (!Array.isArray(child)) continue;
    if (active.has(child)) reject('array cycle');
    if (stack.length >= MAX_DEPTH) reject('array depth');
    active.add(child); stack.push({ value: child, index: 0 });
  }
};

const parents = node => {
  const active = new WeakSet();
  let count = 0;
  while (node && node.type !== 'brace' && node.type !== 'root' && node.parent) {
    if (active.has(node)) reject('parent cycle');
    if (++count > MAX_DEPTH) reject('parent depth');
    active.add(node); node = node.parent;
  }
};

const ast = (root, expand = false) => {
  const active = new WeakSet();
  const stack = [{ node: root, index: -1, child: false }];
  while (stack.length) {
    const frame = stack[stack.length - 1];
    const node = frame.node;
    if (!node || typeof node !== 'object') throw new TypeError('braces: expected an AST node');
    if (frame.index === -1) {
      if (active.has(node)) reject('AST cycle');
      if (stack.length > MAX_DEPTH + 1) reject('AST depth');
      active.add(node);
      array(node.value);
      array(node.ranges);
      array(node.commas);
      // Values are terminal for compile/stringify, and for expand's child loop.
      // Do not reject dormant metadata edges that those walkers never follow.
      if (node.value && (!expand || (frame.child && node.type !== 'open'))) {
        active.delete(node); stack.pop(); continue;
      }
      if (expand) parents(node);
      if (node.nodes && !Array.isArray(node.nodes)) throw new TypeError('braces: expected a nodes array');
      frame.index = 0;
    }
    if (!node.nodes || frame.index === node.nodes.length) {
      active.delete(node); stack.pop(); continue;
    }
    stack.push({ node: node.nodes[frame.index++], index: -1, child: true });
  }
};

// fill-range coerces numeric transform results before append sees them.
const options = opts => {
  array(opts.step);
  array(opts.rangeLimit);
  const descriptors = Object.getOwnPropertyDescriptors(opts);
  // fill-range's own spread ignores inherited/non-enumerable transforms.
  if (!descriptors.transform || !descriptors.transform.enumerable || typeof opts.transform !== 'function') return opts;
  const transform = opts.transform;
  descriptors.transform = { enumerable: true, configurable: true, writable: true, value(...args) {
    const value = transform.apply(this, args);
    array(value);
    return value;
  } };
  return Object.create(Object.getPrototypeOf(opts), descriptors);
};

module.exports = { MAX_DEPTH, nesting, array, ast, reject, options };
