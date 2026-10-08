let openCv = null;
let classifier = null;
let readyPosted = false;

self.Module = self.Module || {};

function postError(message) {
  self.postMessage({ type: 'error', message: String(message) });
}

function postReady() {
  if (readyPosted) return;
  if (!self.cv || !self.cv.Mat || !classifier) return;
  readyPosted = true;
  self.postMessage({ type: 'ready' });
}

function encodeText(text) {
  if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(text);
  const encoded = unescape(encodeURIComponent(text));
  const bytes = new Uint8Array(encoded.length);
  for (let i = 0; i < encoded.length; i += 1) bytes[i] = encoded.charCodeAt(i);
  return bytes;
}

function setupClassifier() {
  try {
    openCv = self.cv;
    if (!openCv || !openCv.Mat) return;
    if (readyPosted) return;
    if (!self.FACE_CASCADE_XML) throw new Error('缺少人脸模型数据');
    const xmlBytes = encodeText(self.FACE_CASCADE_XML);
    openCv.FS_createDataFile('/', 'haarcascade_frontalface_default.xml', xmlBytes, true, false, false);
    classifier = new openCv.CascadeClassifier();
    if (!classifier.load('haarcascade_frontalface_default.xml')) {
      throw new Error('OpenCV 人脸模型加载失败');
    }
    readyPosted = true;
    self.postMessage({ type: 'ready' });
  } catch (error) {
    postError(error && error.message ? error.message : error);
  }
}

function initialize(buffer) {
  try {
    self.Module.wasmBinary = buffer;
    self.Module.onRuntimeInitialized = setupClassifier;
    self.Module.onAbort = (reason) => postError('OpenCV 初始化中止：' + reason);
    importScripts('cascade-data.js');
    importScripts('opencv.js');
    if (self.cv && self.cv.Mat) setupClassifier();
  } catch (error) {
    postError(error && error.message ? error.message : error);
  }
}
function detect(message) {
  let source = null;
  let gray = null;
  let faces = null;
  try {
    if (!openCv || !openCv.Mat || !classifier) {
      throw new Error('OpenCV 尚未初始化');
    }
    const pixels = new Uint8Array(message.buffer);
    source = openCv.matFromArray(message.height, message.width, openCv.CV_8UC4, pixels);
    gray = new openCv.Mat();
    faces = new openCv.RectVector();
    openCv.cvtColor(source, gray, openCv.COLOR_RGBA2GRAY);
    openCv.equalizeHist(gray, gray);
    classifier.detectMultiScale(gray, faces, 1.1, 3, 0, new openCv.Size(64, 64));

    let best = null;
    for (let i = 0; i < faces.size(); i += 1) {
      const rect = faces.get(i);
      if (!best || rect.width * rect.height > best.width * best.height) best = rect;
    }
    if (best) {
      self.postMessage({
        type: 'face',
        found: true,
        x: (best.x + best.width * 0.5) / message.width,
        y: (best.y + best.height * 0.5) / message.height,
        size: best.width / message.width,
      });
    } else {
      self.postMessage({ type: 'face', found: false });
    }
  } catch (error) {
    postError(error && error.message ? error.message : error);
  } finally {
    if (source) source.delete();
    if (gray) gray.delete();
    if (faces) faces.delete();
  }
}

self.onmessage = (event) => {
  const message = event.data || {};
  if (message.type === 'init') {
    initialize(message.wasm);
  } else if (message.type === 'frame') {
    detect(message);
  }
};