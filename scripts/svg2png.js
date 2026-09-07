/**
 * 把 images/ 目录里「内容是 SVG 但扩展名是 .png」的文件，用 Chromium 渲染成真正的 PNG（原地覆盖，文件名不变，doc.md 引用无需改）。
 *
 * 用法：
 *   NODE_PATH="<node workspace>/node_modules" node svg2png.js "<_build>/images"
 * 依赖：playwright（WorkBuddy 托管 node workspace 里已装：C:/Users/Jiazi/.workbuddy/binaries/node/workspace/node_modules）
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const dir = process.argv[2];
  if (!dir) { console.error('usage: node svg2png.js <images_dir>'); process.exit(1); }
  const files = fs.readdirSync(dir).filter(f => {
    const p = path.join(dir, f);
    if (!fs.statSync(p).isFile()) return false;
    return fs.readFileSync(p).slice(0, 64).toString('utf8').includes('<svg');
  });
  if (!files.length) { console.log('no svg found'); process.exit(0); }
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2 });
  for (const f of files) {
    const p = path.join(dir, f);
    const svg = fs.readFileSync(p, 'utf8');
    const m = svg.match(/viewBox=["']\s*([\d.\-]+)[\s,]+([\d.\-]+)[\s,]+([\d.\-]+)[\s,]+([\d.\-]+)/);
    const vb = m ? m.slice(1).map(Number) : [0, 0, 800, 600];
    let w = vb[2], h = vb[3];
    const wm = svg.match(/\bwidth=["'](\d+(?:\.\d+)?)px?["']/);
    const hm = svg.match(/\bheight=["'](\d+(?:\.\d+)?)px?["']/);
    if (wm) w = parseFloat(wm[1]);
    if (hm) h = parseFloat(hm[1]);
    await page.setViewportSize({ width: Math.ceil(w), height: Math.ceil(h) });
    const out = path.join(dir, f.replace(/\.[^.]+$/, '.png'));
    await page.setContent(
      `<html><body style="margin:0;padding:0;background:#fff">${svg}</body></html>`,
      { waitUntil: 'load' }
    );
    const el = await page.$('svg');
    if (el) {
      await page.evaluate(() => {
        const s = document.querySelector('svg');
        s.style.width = '100%';
        s.style.height = 'auto';
        s.style.display = 'block';
      });
      await el.screenshot({ path: out, type: 'png' });
    } else {
      await page.screenshot({ path: out, type: 'png' });
    }
    console.log('converted', f, '->', path.basename(out), fs.statSync(out).size);
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
