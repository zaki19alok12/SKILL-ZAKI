// debug: render frame tertentu ke PNG. usage: node frames.js timeline.json outdir t1 t2 ...
const {chromium}=require('playwright');const fs=require('fs'),path=require('path');
const [,,tlp,outd,...ts]=process.argv;const TL=JSON.parse(fs.readFileSync(tlp,'utf8'));fs.mkdirSync(outd,{recursive:true});
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const p=await b.newPage({viewport:{width:TL.w,height:TL.h}});const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await p.addInitScript(tl=>{window.TL=tl},TL);await p.goto('file://'+path.resolve(__dirname,'engine.html'));await p.evaluate(()=>window.engineReady);
for(const t of ts){const t0=Date.now();await p.evaluate(t=>window.renderFrame(+t),t);await p.screenshot({path:path.join(outd,`t${String(t).padStart(5,'0')}.png`)});console.log(t,Date.now()-t0,'ms')}
if(errs.length)console.log('ERRORS',errs);await b.close()})()
