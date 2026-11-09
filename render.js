// Render frame [start,end) dari timeline.json memakai engine.html -> mp4 tanpa audio.
// usage: node render.js timeline.json start end out.mp4 [layout.json]
const {chromium}=require('playwright');
const {spawn}=require('child_process');
const fs=require('fs'),path=require('path');
const [,, tlPath, s0, s1, out, layoutOut]=process.argv;
const TL=JSON.parse(fs.readFileSync(tlPath,'utf8'));
const start=+s0,end=+s1,FPS=TL.fps;
(async()=>{
  const browser=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--force-color-profile=srgb']});
  const page=await browser.newPage({viewport:{width:TL.w,height:TL.h},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push('pageerror: '+e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push('console: '+m.text())});
  await page.addInitScript(tl=>{window.TL=tl},TL);
  await page.goto('file://'+path.resolve(__dirname,'engine.html'));
  await page.evaluate(()=>window.engineReady);
  const ff=spawn('ffmpeg',['-y','-v','error','-f','image2pipe','-framerate',String(FPS),'-c:v','mjpeg','-i','-',
    '-c:v','libx264','-preset','veryfast','-crf','16','-pix_fmt','yuv420p','-r',String(FPS),'-g','30','-movflags','+faststart',out],{stdio:['pipe','inherit','inherit']});
  const ffDone=new Promise(r=>ff.on('close',r));
  // titik sampling layout: tengah & 85% tiap scene (+ frame pertama)
  const samples=new Map();
  TL.scenes.forEach((sc,i)=>{[0.5,0.9].forEach(f=>{const fr=Math.min(Math.round((sc.t0+(sc.t1-sc.t0)*f)*FPS),Math.round(TL.duration*FPS)-1);samples.set(fr,i)})});
  const layout=[];
  for(let f=start;f<end;f++){
    const t=f/FPS;
    const m=await page.evaluate(t=>window.renderFrame(t),t);
    if(samples.has(f))layout.push(m);
    const buf=await page.screenshot({type:'jpeg',quality:94});
    if(!ff.stdin.write(buf))await new Promise(r=>ff.stdin.once('drain',r));
    if((f-start)%60===0)process.stderr.write(`frame ${f}/${end}\n`);
  }
  ff.stdin.end();await ffDone;await browser.close();
  if(layoutOut)fs.writeFileSync(layoutOut,JSON.stringify({layout,errors},null,1));
  if(errors.length){console.error('ERROR di halaman:\n'+errors.join('\n'));process.exit(2)}
})().catch(e=>{console.error(e);process.exit(1)});
