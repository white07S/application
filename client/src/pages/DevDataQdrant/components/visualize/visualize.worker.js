/* eslint-disable no-restricted-globals */
import * as druid from '@saehrimnir/druidjs';

const DEFAULT_ALGORITHM = 'UMAP';
const MESSAGE_INTERVAL_MS = 200;

function getVectorValue(point, using) {
  if (!using) {
    return point?.vector;
  }
  if (!point?.vector || typeof point.vector !== 'object') {
    return undefined;
  }
  return point.vector[using];
}

function vectorType(value) {
  if (Array.isArray(value)) {
    if (Array.isArray(value[0])) {
      return 'multivector';
    }
    return 'vector';
  }
  if (value && typeof value === 'object') {
    if (Array.isArray(value.indices)) {
      return 'sparse';
    }
    return 'named';
  }
  return 'unknown';
}

function dataset(points, using) {
  const vectors = points.map((point) => getVectorValue(point, using));
  for (let index = 0; index < vectors.length; index += 1) {
    const type = vectorType(vectors[index]);
    if (type === 'vector') {
      continue;
    }
    if (type === 'named') {
      return { error: 'Select a valid vector name with "using"; default vector is not defined' };
    }
    return { error: `Vector visualization is not supported for vector type: ${type}` };
  }

  return { data: vectors };
}

function asCoordinates(values) {
  return values.map((point) => ({ x: point[0], y: point[1] }));
}

self.onmessage = function onmessage(event) {
  const points = event?.data?.points || [];
  const params = event?.data?.params || {};
  const algorithm = params.algorithm || DEFAULT_ALGORITHM;
  const using = params.using || null;

  if (!points || points.length === 0) {
    self.postMessage({ result: [], error: 'No points to visualize' });
    return;
  }

  if (points.length === 1) {
    self.postMessage({ result: [], error: `Cannot perform ${algorithm} on a single point` });
    return;
  }

  const extracted = dataset(points, using);
  if (extracted.error) {
    self.postMessage({ result: [], error: extracted.error });
    return;
  }

  const vectors = extracted.data;
  try {
    if (algorithm === 'PCA') {
      const reducer = new druid.PCA(vectors, {});
      self.postMessage({ result: asCoordinates(reducer.transform()), error: null });
      return;
    }

    const reducer = new druid[algorithm](vectors, {});
    const generator = reducer.generator();
    let reduced = [];
    let last = Date.now();

    for (reduced of generator) {
      if (Date.now() - last > MESSAGE_INTERVAL_MS) {
        last = Date.now();
        self.postMessage({ result: asCoordinates(reduced), error: null });
      }
    }

    self.postMessage({ result: asCoordinates(reduced), error: null });
  } catch (error) {
    self.postMessage({ result: [], error: error?.message || 'Visualization failed' });
  }
};

