// A gesture chooses a station; time, not scroll distance, drives the camera.
(() => {
 const root=document.documentElement, story=document.querySelector('.film-story');
 const main=document.querySelector('#inhalt'), canvas=document.querySelector('canvas'), ctx=canvas.getContext('2d');
 const chapters=[...document.querySelectorAll('.film-chapter')];
 // Approved compositions: entry, project, idea board, comparison, meeting, HTML.
 const stopFrames=[1,49,85,121,157,180];
 const totalFrames=180, contentIndex=chapters.length;
 const stops=stopFrames.map(frame=>(frame-1)/(totalFrames-1));
 const durations=[0,1300,1000,1000,1100,1000];
 const back=document.querySelector('#station-back'), next=document.querySelector('#station-next');
 const count=document.querySelector('#station-count'), status=document.querySelector('#film-status');
 const media=matchMedia('(prefers-reduced-motion:no-preference)');
 const images=new Map();
 const frameRevision='20261102-landscape';
 const glassRevision='20261102-tv-material';
 const frameDirectory=()=>matchMedia('(max-width:900px)').matches?(matchMedia('(orientation:portrait)').matches?'board/':'mobile/') : '';
 let frameVariant=frameDirectory();
 let frameBase=new URL(canvas.dataset.frameBase+frameVariant,document.baseURI);
 const menu=document.querySelector('.home-menu'),readHint=document.querySelector('.chapter-scroll-hint');
 // A single persistent event hero moves between its physical screen and the website.
 const hero=main.querySelector('.event-hero'),mount=main.querySelector('.event-mount');
 const portal=document.createElement('div');portal.className='home-event-layer';portal.hidden=true;portal.setAttribute('aria-hidden','true');portal.inert=true;
 const occluder=document.createElement('canvas'),octx=occluder.getContext('2d');occluder.className='home-event-occluder';occluder.hidden=true;occluder.setAttribute('aria-hidden','true');
 canvas.after(portal);portal.after(occluder);
 const surface=document.createElement('canvas'),sctx=surface.getContext('2d');surface.className='home-screen-glass';surface.hidden=true;surface.setAttribute('aria-hidden','true');occluder.after(surface);
 const reflection=document.createElement('canvas'),rctx=reflection.getContext('2d');reflection.className='home-tv-reflection';reflection.hidden=true;reflection.setAttribute('aria-hidden','true');surface.after(reflection);
 const meetingMedia=root.dataset.meetingMedia||'',screenProjections=new Map();let laptopData=null;
 let meetingPhoto=null,meetingVideo=null,meetingSoundButton=null,mediaPlanes=[];
 if(meetingMedia){
  const photo=document.createElement('img');photo.src=meetingMedia+'group.webp';photo.alt='';
  const video=document.createElement('video');video.src=meetingMedia+'conversation.mp4';video.poster=meetingMedia+'conversation-poster.webp';video.muted=true;video.defaultMuted=true;video.playsInline=true;video.preload='metadata';
  meetingPhoto=photo;meetingVideo=video;meetingSoundButton=document.querySelector('[data-meeting-play]');
  mediaPlanes=[photo,video].map(el=>{const plane=document.createElement('div');plane.className='home-meeting-screen';plane.append(el);portal.append(plane);return plane});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)video.pause();else updateMeetingPlayback()});
  const syncMeetingSoundButton=()=>{if(meetingSoundButton){meetingSoundButton.textContent=video.muted?'Ton einschalten':'Ton ausschalten';meetingSoundButton.setAttribute('aria-pressed',String(!video.muted))}};
  meetingSoundButton?.addEventListener('click',()=>{video.muted=!video.muted;if(!video.muted&&video.paused)video.play().catch(()=>{video.muted=true});syncMeetingSoundButton()});
  video.addEventListener('volumechange',syncMeetingSoundButton);syncMeetingSoundButton();
 }
 let mediaWasAtStation=false;
 function updateMeetingPlayback(){
  if(!meetingVideo)return;
  const atStation=active&&!moving&&index===3&&media.matches&&!document.hidden;
  if(atStation&&!mediaWasAtStation)meetingVideo.play().catch(()=>{});
  if(!atStation){meetingVideo.pause();meetingVideo.muted=true;if(meetingVideo.readyState>0&&meetingVideo.currentTime)meetingVideo.currentTime=0;}
  mediaWasAtStation=atStation;
 }
 function loadLaptopData(){
  if(!meetingMedia)return Promise.resolve();
  const variant=frameVariant,base=frameBase;
  if(!screenProjections.has(variant))screenProjections.set(variant,fetch(new URL('screens.json',base)).then(r=>{if(!r.ok)throw Error('Laptop projection unavailable');return r.json()}));
  return screenProjections.get(variant).then(data=>{if(variant===frameVariant)laptopData=data});
 }
 const projections=new Map();let boardData=null;
 function loadBoardData(){
  const variant=frameVariant,base=frameBase,total=variant==='board/'?157:180;
  if(!projections.has(variant))projections.set(variant,fetch(new URL('projection.json',base)).then(r=>{if(!r.ok)throw Error('Screen projection unavailable');return r.json()}).then(data=>{for(let f=1;f<=total;f++)if(!Array.isArray(data[f])||data[f].length!==4||!data[f].every(p=>p.length===2&&p.every(Number.isFinite)))throw Error('Invalid screen projection');return data}));
  return projections.get(variant).then(data=>{if(variant===frameVariant)boardData=data;return data});
 }
 function heroLayout(){
  const portrait=frameVariant==='board/',width=portrait?390:1280,height=portrait?693.333333:720;
  const available=mount.clientWidth||innerWidth;hero.dataset.layout=portrait?'portrait':'wide';hero.style.width=width+'px';hero.style.height=height+'px';mount.style.height=height*available/width+'px';
  root.style.setProperty('--nav-height',document.querySelector('.film-nav').offsetHeight+'px');return {width,height,scale:available/width};
 }
 function returnHero(){if(hero.parentNode!==mount)mount.append(hero);const {scale}=heroLayout();hero.style.transform=`scale(${scale})`;hero.style.setProperty('--open','1');hero.style.removeProperty('clip-path');hero.style.setProperty('--screen-presence','0');}
 let active=false, moving=false, loading=false, index=0, progress=0, generation=0, desired=1, raf=0;
 let lastWheel=-Infinity, wheelUsed=false, wheelReading=false, wheelSum=0, touch=null;
 const boundary=()=>story.offsetHeight-story.querySelector('.film-stage').offsetHeight;
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 function getFrame(n){
  if(images.has(n))return images.get(n);
  const variant=frameVariant,base=frameBase;
  const load=(prefix)=>new Promise((resolve,reject)=>{
   const image=new Image(); image.onload=()=>resolve(image); image.onerror=reject;
   const url=new URL(`${prefix}-${String(n).padStart(4,'0')}.webp`,base);
   if(prefix==='frame')url.searchParams.set('v',frameRevision);
   if(prefix==='glass')url.searchParams.set('v',glassRevision);
   image.src=url.href;
  });
  const promise=Promise.all([load('frame'),load('mask'),load('glass'),loadBoardData(),meetingMedia?load('laptops'):Promise.resolve(null),loadLaptopData()]).then(([image,mask,glass,_,laptops])=>{image.boardMask=mask;image.screenGlass=glass;image.laptopMask=laptops;return image});
  images.set(n,promise);
  if(images.size>64){
   [...images.keys()].sort((a,b)=>Math.abs(b-desired)-Math.abs(a-desired)).slice(0,images.size-64).forEach(k=>images.delete(k));
  }
  return promise;
 }
 function fallback(){
  const hadFocus=chapters.some(e=>e.contains(document.activeElement));
  active=false;moving=false;loading=false;generation++;cancelAnimationFrame(raf);
  root.classList.remove('film-active','content-ready','is-travelling','is-mobile-portal','is-event-opening');portal.hidden=occluder.hidden=surface.hidden=reflection.hidden=true;updateMeetingPlayback();returnHero();
  canvas.style.removeProperty('transform');
  readHint.hidden=true;
  main.inert=false;main.removeAttribute('style');
  chapters.forEach(e=>{e.inert=false;e.removeAttribute('aria-hidden');e.removeAttribute('data-visible');e.removeAttribute('style')});
  back.disabled=next.disabled=false;status.textContent='Ruhige Ansicht';
  if(hadFocus)document.activeElement.scrollIntoView({block:'center'});
 }
 function rememberStation(){
  const hash=index===contentIndex?'#inhalt':`#${chapters[index].id}`;
  if(location.hash!==hash)history.replaceState(null,'',hash);
 }
 function rememberReadingPosition(){
  if(active&&index===contentIndex&&!moving)history.replaceState({homeScroll:scrollY},'',location.href);
 }
 function restoreReadingPosition(){
  if(active&&index===contentIndex&&location.hash==='#inhalt'&&Number.isFinite(history.state?.homeScroll)){
   scrollTo({top:Math.max(boundary(),history.state.homeScroll),behavior:'instant'});draw();
  }
 }
 function readingHint(){
  const box=chapters[index];
  chapters.forEach(e=>e.classList.toggle('has-overflow',e.scrollHeight>e.clientHeight+2));
  readHint.hidden=!active||moving||index===4||!box||box.scrollHeight-box.clientHeight-box.scrollTop<5;
 }
 chapters.forEach(box=>box.addEventListener('scroll',readingHint,{passive:true}));
 if('ResizeObserver' in window){
  const copyObserver=new ResizeObserver(readingHint);
  chapters.forEach(box=>copyObserver.observe(box.querySelector('.wow-copy')));
 }
 function boardPoints(frame,img,raw=boardData[frame]){
  const portrait=frameVariant==='board/',fit=portrait?Math.max(canvas.clientWidth/img.naturalWidth,canvas.clientHeight/img.naturalHeight):canvas.clientWidth/img.naturalWidth;
  const left=(canvas.clientWidth-img.naturalWidth*fit)/2;
  return raw.map(([x,y])=>[canvas.offsetLeft+left+x*fit,canvas.offsetTop+y*fit]);
 }
 // Homography from a CSS rectangle to the four rendered screen corners.
 function boardMatrix(points,width,height){
  const [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]=points;
  const dx1=x1-x2,dx2=x3-x2,dx3=x0-x1+x2-x3,dy1=y1-y2,dy2=y3-y2,dy3=y0-y1+y2-y3;
  const den=dx1*dy2-dx2*dy1;
  if(Math.abs(den)<.00001)return null;
  const g=(dx3*dy2-dx2*dy3)/den,h=(dx1*dy3-dx3*dy1)/den;
  return `matrix3d(${(x1-x0+g*x1)/width},${(y1-y0+g*y1)/width},0,${g/width},${(x3-x0+h*x3)/height},${(y3-y0+h*y3)/height},0,${h/height},0,0,1,0,${x0},${y0},0,1)`;
 }
 function drawBoard(frame,img){
  if(!boardData||!img.boardMask)return;
  if(index===contentIndex&&!moving){portal.hidden=occluder.hidden=surface.hidden=reflection.hidden=true;canvas.style.removeProperty('transform');root.classList.remove('is-event-opening');returnHero();return}
  const {width,height}=heroLayout();if(hero.parentNode!==portal)portal.append(hero);
  let points=boardPoints(frame,img),t=clamp((progress-stops[4])/(1-stops[4]),0,1);
  portal.hidden=occluder.hidden=surface.hidden=reflection.hidden=false;root.classList.toggle('is-event-opening',t>0);
  const opening=clamp((t-.68)/.32,0,1);hero.style.setProperty('--open',String(opening));hero.style.setProperty('--screen-presence',String(1-t));
  if(frameVariant==='board/'&&t>0){
   const [x0,y0]=points[0],initial=(points[1][0]-x0)/width,end=innerWidth/width,scale=initial+(end-initial)*t;
   const nav=document.querySelector('.film-nav').offsetHeight,x=x0*(1-t),y=y0*(1-t)+nav*t,z=scale/initial;
   const tx=x-x0*z+canvas.offsetLeft*(z-1),ty=y-y0*z+canvas.offsetTop*(z-1);
   canvas.style.transform=occluder.style.transform=surface.style.transform=reflection.style.transform=`translate(${tx}px,${ty}px) scale(${z})`;
   points=[[x,y],[x+width*scale,y],[x+width*scale,y+height*scale],[x,y+height*scale]];
  }else{canvas.style.removeProperty('transform');occluder.style.removeProperty('transform');surface.style.removeProperty('transform');reflection.style.removeProperty('transform')}
  hero.style.transform=boardMatrix(points,width,height);
  // Match the photographic room's sampling at a distance. CSS text otherwise
  // stays pin-sharp while the rendered board beside it is softly resampled.
  // Express blur in the screen's own coordinates, before the perspective warp;
  // fade it completely before the screen becomes the interactive website.
  const screenScale=Math.hypot(points[1][0]-points[0][0],points[1][1]-points[0][1])/width;
  const roomScale=frameVariant==='board/'?Math.max(canvas.clientWidth/img.naturalWidth,canvas.clientHeight/img.naturalHeight):canvas.clientWidth/img.naturalWidth;
  const distanceSoftness=.85*roomScale*(1-clamp(screenScale/roomScale,0,1));
  hero.style.setProperty('--screen-softness',`${distanceSoftness/Math.max(screenScale,.05)*Math.pow(1-t,2)}px`);
  if(meetingMedia&&laptopData){
   mediaPlanes.forEach((plane,i)=>{const ps=boardPoints(frame,img,laptopData[frame][i+1]);plane.style.transform=boardMatrix(ps,1024,629);plane.hidden=t>0;});
  }hero.style.clipPath=`inset(${width*.0025*(1-t)}px)`;
  if(occluder.width!==img.naturalWidth||occluder.height!==img.naturalHeight){occluder.width=img.naturalWidth;occluder.height=img.naturalHeight}
  octx.globalCompositeOperation='copy';octx.drawImage(img,0,0);octx.globalCompositeOperation='destination-out';octx.drawImage(img.boardMask,0,0,occluder.width,occluder.height);if(meetingMedia&&img.laptopMask&&t===0)octx.drawImage(img.laptopMask,0,0,occluder.width,occluder.height);
  octx.globalCompositeOperation='source-over';occluder.dataset.frame=String(frame);
  if(surface.width!==img.naturalWidth||surface.height!==img.naturalHeight){surface.width=img.naturalWidth;surface.height=img.naturalHeight}
  // Preserve the laptop treatment; the TV has its own dielectric reflection pass.
  sctx.clearRect(0,0,surface.width,surface.height);
  if(meetingMedia&&img.laptopMask&&t===0){
   sctx.globalCompositeOperation='copy';sctx.drawImage(img.laptopMask,0,0,surface.width,surface.height);
   sctx.globalCompositeOperation='source-in';sctx.drawImage(img.screenGlass,0,0,surface.width,surface.height);
  }sctx.globalCompositeOperation='source-over';
  surface.style.opacity=String(.26*Math.pow(1-t,2));surface.dataset.frame=String(frame);
  if(reflection.width!==img.naturalWidth||reflection.height!==img.naturalHeight){reflection.width=img.naturalWidth;reflection.height=img.naturalHeight}
  rctx.globalCompositeOperation='copy';rctx.drawImage(img.boardMask,0,0,reflection.width,reflection.height);
  rctx.globalCompositeOperation='source-in';rctx.drawImage(img.screenGlass,0,0,reflection.width,reflection.height);rctx.globalCompositeOperation='source-over';
  // Screen blending adds reflected light to the emitted content. A normal
  // translucent overlay would turn every dark pixel into a uniform grey veil.
  reflection.style.opacity=String(.72*Math.pow(1-t,2));reflection.dataset.frame=String(frame);
 }
 function draw(){
  const portalProgress=clamp((progress-stops[4])/(1-stops[4]),0,1);
  // A short landscape screen retains the complete display above the controls.
  // The viewport expands to the website width during the existing final flight.
  if(frameVariant==='mobile/'){
   const roomHeight=Math.max(160,innerHeight-document.querySelector('.film-nav').offsetHeight-80);
   const fitted=Math.min(innerWidth,roomHeight*16/9),width=fitted+(innerWidth-fitted)*portalProgress;
   for(const layer of [canvas,occluder,surface,reflection]){layer.style.width=width+'px';layer.style.left=(innerWidth-width)/2+'px'}
  }else for(const layer of [canvas,occluder,surface,reflection]){layer.style.removeProperty('width');layer.style.removeProperty('left')}

  const token=generation, frame=desired=frameVariant==='board/'&&progress>=stops[4]?157:1+Math.round(progress*(totalFrames-1));
  getFrame(frame).then(img=>{
   if(!active||generation!==token||desired!==frame)return;
   if(canvas.width!==img.naturalWidth||canvas.height!==img.naturalHeight){canvas.width=img.naturalWidth;canvas.height=img.naturalHeight}
   ctx.drawImage(img,0,0);canvas.dataset.frame=String(frame);
   drawBoard(frame,img);

  }).catch(()=>{if(active&&generation===token)fallback()});
  root.dataset.station=String(index);root.dataset.travelling=String(moving);
  root.style.setProperty('--portal-scale',String(innerWidth/1280));
  chapters.forEach((e,i)=>{
   const visible=!moving&&index===i;
   e.dataset.visible=String(visible);e.inert=!visible;e.setAttribute('aria-hidden',String(!visible));
   e.style.setProperty('--chapter-opacity',visible?'1':'0');
  });

  const opacity=index===contentIndex&&!moving?1:0;
  main.style.setProperty('--content-opacity',String(opacity));
  main.style.setProperty('--content-shift',`${-Math.max(0,boundary()-scrollY)}px`);
  const ready=index===contentIndex&&!moving;
  main.inert=!ready;root.classList.toggle('content-ready',ready);
  back.disabled=moving||index===0;next.disabled=moving||index===contentIndex;
  const label=index===contentIndex?'Inhalt':`${index+1} / ${contentIndex}`;
  if(count.textContent!==label)count.textContent=label;
  next.textContent=loading?'Lädt …':index===contentIndex-1?'Zum Inhalt →':'Weiter →';
  status.textContent=loading?'Ansicht lädt …':moving?'Kamera fährt …':index===contentIndex?'Weiter zum Inhalt':matchMedia('(max-width:900px)').matches?'Wischen · nächste Station':'Scrollen oder wischen · eine Station weiter';
  readingHint();updateMeetingPlayback();
 }
 function go(target,instant=false,focus=false){
  if(!active||moving&&!instant)return;
  target=clamp(target,0,contentIndex);
  const previous=index;
  if(target===index&&!instant)return;
  cancelAnimationFrame(raf);generation++;
  const token=generation, from=progress, to=stops[target];
  index=target; moving=!instant;loading=!instant;
  root.classList.toggle('is-travelling',moving);
  if(previous===contentIndex||scrollY>0)scrollTo({top:0,behavior:'instant'});
  if(chapters.some(e=>e.contains(document.activeElement))){next.focus({preventScroll:true})}
  const finish=()=>{
   if(token!==generation||!active)return;
   progress=to;moving=false;loading=false;root.classList.remove('is-travelling');
   if(!instant)rememberStation();
   if(index===contentIndex)scrollTo({top:boundary(),behavior:'instant'});
   else chapters[index].scrollTop=0;
   draw();
   if(focus||index===contentIndex){const el=index===contentIndex?main:chapters[index];el.tabIndex=-1;el.focus({preventScroll:true})}
  };
  if(instant){finish();return}
  draw();
  // Load only the upcoming segment, bounded by the cache, before its timed flight.
  const cap=frameVariant==='board/'?157:totalFrames;
  const first=Math.min(cap,1+Math.round(Math.min(from,to)*(totalFrames-1))),last=Math.min(cap,1+Math.round(Math.max(from,to)*(totalFrames-1)));
  Promise.all(Array.from({length:last-first+1},(_,i)=>getFrame(first+i))).then(()=>{
   if(token!==generation||!active)return;
   loading=false;
   const started=performance.now(),duration=frameVariant==='board/'&&Math.max(target,previous)===contentIndex?1450:durations[Math.max(target,previous)];
   function tick(now){
    if(token!==generation||!active)return;
    const t=clamp((now-started)/duration,0,1),ease=t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
    progress=from+(to-from)*ease;draw();
    if(t<1)raf=requestAnimationFrame(tick);else finish();
   }
   raf=requestAnimationFrame(tick);
  }).catch(()=>{if(token===generation)fallback()});
 }
 function inJourney(direction){return active&&(index<contentIndex||moving||(direction<0&&scrollY<=boundary()+2))}
 function canRead(target,direction){
  const box=target.closest?.('.film-chapter');
  return box&&box.id!=='wow-treffen'&&!moving&&(direction>0?box.scrollTop+box.clientHeight<box.scrollHeight-2:box.scrollTop>2);
 }
 addEventListener('wheel',event=>{
  if(menu.open)return;
  if(event.ctrlKey||Math.abs(event.deltaX)>Math.abs(event.deltaY)||!event.deltaY)return;
  const dir=Math.sign(event.deltaY),now=performance.now();
  if(now-lastWheel>240){wheelUsed=false;wheelReading=false;wheelSum=0}
  lastWheel=now;
  // The gesture that entered the TV ends here, even if its momentum outlasts the flight.
  if(active&&wheelUsed&&index===contentIndex&&scrollY<=boundary()+2){event.preventDefault();return}
  if(!inJourney(dir))return;
  // A gesture started inside long copy stays a reading gesture through its tail.
  if(wheelReading)return;
  if(!wheelUsed&&canRead(event.target,dir)){wheelReading=true;return}
  event.preventDefault();
  if(wheelUsed)return;
  if(moving){wheelUsed=true;return}
  wheelSum+=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?innerHeight:1);
  if(Math.abs(wheelSum)>=30){wheelUsed=true;go(index+dir)}
 },{passive:false});
 addEventListener('touchstart',event=>{
  touch=event.touches.length===1?{x:event.touches[0].clientX,y:event.touches[0].clientY,target:event.target,mode:null,used:false}:null;
 },{passive:true});
 addEventListener('touchmove',event=>{
  if(!touch||event.touches.length!==1)return;
  const dx=touch.x-event.touches[0].clientX,dy=touch.y-event.touches[0].clientY,dir=Math.sign(dy);
  if(touch.mode===null&&Math.max(Math.abs(dx),Math.abs(dy))>10){
   touch.mode=menu.open||Math.abs(dx)>Math.abs(dy)||!inJourney(dir)||canRead(touch.target,dir)?'native':'station';
  }
  if(touch.mode!=='station')return;
  event.preventDefault();
  if(!touch.used&&Math.abs(dy)>42){touch.used=true;if(!moving)go(index+dir)}
 },{passive:false});
 addEventListener('touchend',()=>{touch=null},{passive:true});
 addEventListener('touchcancel',()=>{touch=null},{passive:true});
 addEventListener('keydown',event=>{
  if(event.key==='Escape'&&menu.open){menu.open=false;menu.querySelector('summary').focus();return}
  if(menu.open||event.altKey||event.ctrlKey||event.metaKey||event.target.closest('input,textarea,select,button,summary,[contenteditable="true"]')||event.key===' '&&event.target.closest('a'))return;
  const dir=['ArrowDown','PageDown',' '].includes(event.key)?(event.shiftKey?-1:1):['ArrowUp','PageUp'].includes(event.key)?-1:0;
  if(!dir||!inJourney(dir)||canRead(event.target,dir))return;
  event.preventDefault();if(!event.repeat&&!moving)go(index+dir,false,true);
 });
 back.addEventListener('click',()=>go(index-1));next.addEventListener('click',()=>go(index+1));
 function fragment(hash,focus=false){
  const detail=hash&&document.querySelector(hash);
  if(detail&&detail!==main&&main.contains(detail)&&active){
   go(contentIndex,true);
   detail.tabIndex=-1;
   requestAnimationFrame(()=>{detail.scrollIntoView({block:'start',behavior:'instant'});if(focus)detail.focus({preventScroll:true});rememberReadingPosition()});
   return true;
  }
  const i=hash==='#inhalt'?contentIndex:!hash||hash==='#top'?0:chapters.findIndex(e=>`#${e.id}`===hash);
  if(i<0||!active)return false;
  go(i,true,focus);return true;
 }
 document.addEventListener('click',event=>{
  if(!menu.contains(event.target)||event.target.closest('a'))menu.open=false;
  const link=event.target.closest('a[href^="#"]');
  if(!link||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  rememberReadingPosition();
  if(fragment(link.hash,true)){event.preventDefault();if(location.hash!==link.hash)history.pushState(null,'',link.hash)}

 });
 addEventListener('hashchange',()=>{if(fragment(location.hash,true))restoreReadingPosition()});
 // Keep only this document's reading offset in its normal browser-history entry.
 addEventListener('pagehide',rememberReadingPosition);
 addEventListener('scroll',()=>{
  if(!active||moving)return;
  // Scrollbar, accessibility navigation and history restoration still have an exit.
  if(index<contentIndex&&scrollY>=boundary()-2){index=contentIndex;progress=1;rememberStation();draw()}
  else if(index===contentIndex&&scrollY<boundary()-3)go(contentIndex-1);
  else if(index===contentIndex)main.style.setProperty('--content-shift','0px');
 },{passive:true});
 addEventListener('resize',()=>{
  const variant=frameDirectory();
  if(variant!==frameVariant){
   frameVariant=variant;frameBase=new URL(canvas.dataset.frameBase+variant,document.baseURI);images.clear();boardData=null;
   // A rotation settles at the chosen station; stale landscape loads cannot draw over it.
   if(active){
    if(index!==contentIndex||moving){go(index,true);rememberStation();return}
    generation++; // In normal content, keep the browser's reading offset on rotation.
   }
  }
  if(active){if(index===contentIndex&&!moving&&scrollY<boundary())scrollTo(0,boundary());draw()}
 },{passive:true});
 async function configure(){
  fallback();if(!ctx||!media.matches)return;
  const token=generation;
  try{
   const pageReady=document.readyState==='complete'?Promise.resolve():new Promise(resolve=>addEventListener('load',resolve,{once:true}));
   await Promise.all([getFrame(1),document.fonts.ready,pageReady]);
   // Let the browser finish its initial anchor jump before replacing the long fallback layout.
   await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
   if(token!==generation||!media.matches)return;
   active=true;index=0;progress=0;root.classList.add('film-active');
   if(!fragment(location.hash)){
    if(scrollY>=boundary()-2){index=contentIndex;progress=1}
    draw();
   }
   restoreReadingPosition();
  }catch{fallback()}
 }
 document.addEventListener('kiwerk:events',()=>{if(active)draw();else returnHero()});
 media.addEventListener('change',configure);configure();
})();
