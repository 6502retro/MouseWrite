// Persistent apple2js harness. node harness.js <port> <hdd-url> [floppy-url]
// HTTP POST / with JSON {cmds:[...]}; each cmd: ["wait",s] ["shot",name] ["text"] ["key","str"] ["keycode",n]
// ["move",x,y] (apple 560x384 coords) ["down"] ["up"] ["click",x,y] ["eval","js"] ["save",drive,path] ["peek",addr,len]
// ["oa",bool] ["sa",bool] (open/solid apple) ["speed",khz] ["floppy",drive,url] ["hdd",drive,url] ["waittext",regex,timeout]
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const [port, hdd, flop] = process.argv.slice(2);
const SHOTS = process.env.SHOTS || '/tmp';
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  await page.route(u => !u.href.startsWith('http://localhost'), r => r.abort());
  page.on('console', m => { if (m.type() === 'error') console.log('console:', m.text()); });
  await page.addInitScript(() => { try { localStorage.setItem('gl_canvas', 'false'); } catch (e) {} });
  let url = 'http://localhost:8765/apple2jse.html';
  if (hdd) url += '#' + hdd;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => window.__a2, null, { timeout: 30000 });
  if (flop) {
    await page.evaluate(async (u) => { const b = await (await fetch(u)).arrayBuffer(); await window.__a2.disk2.setBinary(1, 'f', u.split('.').pop().toLowerCase(), b); }, flop);
  }
  const textScreen = () => page.evaluate(() => {
    const m = window.__a2.apple2.getMMU();
    const main = m.mem04_07[0], aux = m.mem04_07[1];
    const vm = window.__a2.apple2.getVideoModes();
    const col80 = vm._80col !== undefined ? vm._80col : true;
    const lines = [];
    for (let r = 0; r < 24; r++) {
      const base = 0x400 + (r & 7) * 0x80 + (r >> 3) * 0x28;
      let s = '';
      for (let c = 0; c < 40; c++) {
        const a = base + c, pg = a >> 8, off = a & 255;
        const ch = (x) => { x = x & 0xff; let y = x & 0x7f; if (x < 0x80 && y >= 0x40 && y < 0x60) return String.fromCharCode(0x2500 + (y - 0x40)); if (y < 0x20) y += 0x40; return String.fromCharCode(y); };
        s += (col80 ? ch(aux.read(pg, off)) : '') + ch(main.read(pg, off));
      }
      lines.push(s);
    }
    return lines.join('\n');
  });
  const shot = async (name) => { const p = `${SHOTS}/${name}.png`; await page.locator('#screen').screenshot({ path: p }); return p; };
  const run = async (cmds) => {
    const out = [];
    for (const c of cmds) {
      const [op, ...a] = c;
      if (op === 'wait') await page.waitForTimeout(a[0] * 1000);
      else if (op === 'shot') out.push(await shot(a[0]));
      else if (op === 'text') out.push(await textScreen());
      else if (op === 'key') {
        for (const ch of a[0]) {
          const code = ch === '\n' ? 13 : ch.charCodeAt(0);
          await page.evaluate((k) => { window.__a2.io.keyDown(k); }, code);
          await page.waitForTimeout(a[1] || 120);
          await page.evaluate(() => window.__a2.io.keyUp());
          await page.waitForTimeout(40);
        }
      } else if (op === 'keycode') {
        await page.evaluate((k) => window.__a2.io.keyDown(k), a[0]);
        await page.waitForTimeout(a[1] || 150);
        await page.evaluate(() => window.__a2.io.keyUp());
        await page.waitForTimeout(60);
      } else if (op === 'oa') await page.evaluate((s) => window.__a2.io.buttonDown(0, s), a[0]);
      else if (op === 'sa') await page.evaluate((s) => window.__a2.io.buttonDown(1, s), a[0]);
      else if (op === 'move') {
        const steps = a[2] || 12;
        const cur = await page.evaluate(() => window.__mpos || [280, 192]);
        for (let i = 1; i <= steps; i++) {
          const x = cur[0] + (a[0] - cur[0]) * i / steps, y = cur[1] + (a[1] - cur[1]) * i / steps;
          await page.evaluate(([x, y]) => { window.__a2.mouse.setMouseXY(x, y, 560, 384); window.__mpos = [x, y]; }, [x, y]);
          await page.waitForTimeout(30);
        }
      } else if (op === 'down') { await page.evaluate(() => window.__a2.mouse.setMouseDown(true)); await page.waitForTimeout(100); }
      else if (op === 'up') { await page.evaluate(() => window.__a2.mouse.setMouseDown(false)); await page.waitForTimeout(100); }
      else if (op === 'eval') out.push(await page.evaluate(a[0]));
      else if (op === 'peek') out.push(await page.evaluate(([ad, n, bank]) => { const m = window.__a2.apple2.getMMU(); const r = []; for (let i = 0; i < n; i++) { const x = ad + i; r.push(bank === 'aux' ? m._pages ? m.mem60_BF[1].read(x >> 8, x & 255) : 0 : window.__a2.cpu.read(x >> 8, x & 255)); } return r.map(v => v.toString(16).padStart(2, '0')).join(' '); }, [a[0], a[1], a[2]]));
      else if (op === 'save') {
        const b64 = await page.evaluate(async (d) => { const r = await window.__a2.smartport.getBinary(d); const u = new Uint8Array(r.data); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); }, a[0]);
        fs.writeFileSync(a[1], Buffer.from(b64, 'base64')); out.push('saved ' + a[1]);
      } else if (op === 'floppy') {
        await page.evaluate(async ([d, u]) => { const b = await (await fetch(u)).arrayBuffer(); await window.__a2.disk2.setBinary(d, 'f', u.split('.').pop().toLowerCase(), b); }, [a[0], a[1]]); out.push('inserted');
      } else if (op === 'hdd') {
        await page.evaluate(async ([d, u]) => { const b = await (await fetch(u)).arrayBuffer(); await window.__a2.smartport.setBinary(d, 'h', u.split('.').pop().toLowerCase(), b); }, [a[0], a[1]]); out.push('mounted');
      } else if (op === 'waittext') {
        const re = new RegExp(a[0]); const t0 = Date.now(); let t = '';
        while (Date.now() - t0 < (a[1] || 60) * 1000) { t = await textScreen(); if (re.test(t)) break; await page.waitForTimeout(500); }
        out.push((re.test(t) ? 'FOUND ' : 'TIMEOUT ') + ((Date.now() - t0) / 1000).toFixed(1) + 's');
      } else if (op === 'reload') {
        await page.goto('about:blank'); let u = 'http://localhost:8765/apple2jse.html'; if (a[0]) u += '#' + a[0];
        await page.goto(u, { waitUntil: 'domcontentloaded' }); await page.waitForFunction(() => window.__a2, null, { timeout: 30000 }); out.push('reloaded');
      }
    }
    return out;
  };
  http.createServer((req, res) => {
    let body = ''; req.on('data', d => body += d);
    req.on('end', async () => {
      try { const r = await run(JSON.parse(body).cmds); res.end(JSON.stringify(r)); }
      catch (e) { res.end(JSON.stringify(['ERR ' + e.stack])); }
    });
  }).listen(+port, () => console.log('harness ready', port));
})();
