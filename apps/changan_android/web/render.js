// Cache a short window of decoded H3 frames. Frame geometry is shared with Windows.
const atlasPages = new Map();
function atlasPage(path) {
  let item = atlasPages.get(path);
  if (!item) {
    const img = new Image();
    item = {
      img,
      ready: new Promise((ok, fail) => {
        img.onload = ok;
        img.onerror = () => fail(Error("画面载入失败 " + path));
      })
    };
    atlasPages.set(path, item);
    img.src = path;
  }
  atlasPages.delete(path);
  atlasPages.set(path, item);
  if (atlasPages.size > (typeof LanternFilm === "undefined" ? 10 : 5)) {
    const oldest = atlasPages.keys().next().value;
    const evicted = atlasPages.get(oldest);
    atlasPages.delete(oldest);
    if (typeof LanternFilm !== "undefined" && evicted.img.complete)
      evicted.img.src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";
  }
  return item;
}
function drawAtlas(context, bank, frame) {
  const bounded = Math.min(bank.frames - 1, Math.max(0, frame));
  const page = Math.floor(bounded / 12), cell = bounded % 12, item = atlasPage(bank.pages[page]);
  if (page + 1 < bank.pages.length) atlasPage(bank.pages[page + 1]).ready.catch(error);
  if (!item.img.complete || !item.img.naturalWidth) return false;
  context.drawImage(
      item.img, (cell % 4) * bank.width, Math.floor(cell / 4) * bank.height, bank.width, bank.height, 0, 0,
      context.canvas.width, context.canvas.height);
  return true;
}
function readMask(buffer, clip) {
  const view = new DataView(buffer);
  let offset = 36;
  function u16() {
    const n = view.getUint16(offset, true);
    offset += 2;
    return n;
  }
  const bytes = new Uint8Array(buffer);
  const sha = Array.from(bytes.slice(4, 36), x => x.toString(16).padStart(2, "0")).join("");
  if (String.fromCharCode(...bytes.slice(0, 4)) !== "DCM1" || sha !== clip.sha256 || u16() !== clip.frames)
    throw Error("视频判定数据与版本不匹配");
  const frames = [];
  for (let f = 0; f < clip.frames; f++) {
    const spans = [];
    for (let n = u16(); n--;) {
      spans.push([u16(), u16(), u16()]);
    }
    frames.push(spans);
  }
  if (offset !== buffer.byteLength) throw Error("判定数据长度异常");
  return frames;
}
function hitsMask(spans, p, margin) {
  return spans.some(([y, x, end]) => {
    const dx = Math.max(2 * x - p.x, 0, p.x - (end * 2 - 1)), dy = Math.max(2 * y - p.y, 0, p.y - 2 * y - 1);
    return dx * dx + dy * dy <= margin * margin;
  });
}
function inPolygon(poly, p) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [x, y] = poly[i], [u, v] = poly[j];
    if ((y > p.y) !== (v > p.y) && p.x < (u - x) * (p.y - y) / (v - y) + x) inside = !inside;
  }
  return inside;
}
function nearPolygon(poly, p, radius) {
  return poly.some(([x, y], i) => {
    const [u, v] = poly[(i + 1) % poly.length], dx = u - x, dy = v - y;
    const at =
        Math.max(0, Math.min(1, ((p.x - x) * dx + (p.y - y) * dy) / Math.max(.0001, dx * dx + dy * dy)));
    return Math.hypot(p.x - x - at * dx, p.y - y - at * dy) <= radius;
  });
}
