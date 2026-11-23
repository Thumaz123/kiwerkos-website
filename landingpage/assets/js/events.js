(function(global){
 'use strict';
 function todayISO(now=new Date()){const p=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);return ['year','month','day'].map(k=>p.find(x=>x.type===k).value).join('-')}
 function upcoming(config,today,count=3){let [y,m]=today.split('-').map(Number);const events=[];for(let i=0;i<count+240;i++){const first=new Date(Date.UTC(y,m-1,1)),day=1+(4-first.getUTCDay()+7)%7,date=`${y}-${String(m).padStart(2,'0')}-${String(day).padStart(2,'0')}`;if(date>=today&&date>=config.start){const override=config.overrides?.[date]||{};if((override.visibility||'public')==='public')events.push(Object.assign({date,city:config.city,price:config.price,status:'planned',venue:null,address:null,time:null,capacity:null,ticket_url:null,ticket_verified:false,booking_opens:null},override));if(events.length===count)return events}if(++m===13){m=1;y++}}return events}
 // Online-Treffen: dritter Donnerstag im Monat, also zwei Wochen nach dem Präsenztreffen.
 function online(config,today,count=3){const o=config.online;if(!o||!o.start)return [];let [y,m]=today.split('-').map(Number);const events=[];for(let i=0;i<count+240&&events.length<count;i++){const first=new Date(Date.UTC(y,m-1,1)),day=15+(4-first.getUTCDay()+7)%7,date=`${y}-${String(m).padStart(2,'0')}-${String(day).padStart(2,'0')}`;if(date>=today&&date>=o.start&&!(o.excluded||[]).includes(date))events.push({date,online:true,city:o.label||'Online',price:o.price,status:'planned',time:o.time||null,registration_url:(o.registration_urls||{})[date]||o.registration_url||null});if(++m===13){m=1;y++}}return events}
 function schedule(config,today,count=6){return upcoming(config,today,count).concat(online(config,today,count)).sort((a,b)=>a.date<b.date?-1:a.date>b.date?1:0).slice(0,count)}
 function booking(e,today){if(e.status==='cancelled')return ['Abgesagt',null];let safe=false;try{const u=new URL(e.ticket_url);safe=u.protocol==='https:'&&['eventfrog.de','www.eventfrog.de','eventfrog.ch','www.eventfrog.ch'].includes(u.hostname)&&!u.username&&!u.password}catch{}return e.status==='confirmed'&&e.ticket_verified===true&&safe&&['venue','time'].every(k=>typeof e[k]==='string'&&e[k].trim())&&(!e.booking_opens||today>=e.booking_opens)?['Tickets buchen',e.ticket_url]:[e.status==='planned'&&!(e.price>0)?'Details folgen':'Tickets folgen',null]}
 function onlineRegistration(url){try{const u=new URL(url);return u.protocol==='https:'&&u.hostname.endsWith('.sibforms.com')&&u.pathname.startsWith('/serve/')&&!u.username&&!u.password?u.href:null}catch{return null}}
 const short=iso=>iso.slice(8,10)+'.'+iso.slice(5,7)+'.';
 function updateButton(old,e,today){const [label,url]=booking(e,today),el=document.createElement(url?'a':'button');el.className='ticket-button';el.textContent=url?label+' · Eventfrog':label;if(url){el.href=url;el.target='_blank';el.rel='noopener noreferrer'}else{el.type='button';el.disabled=true}old.replaceWith(el)}
 function updateDetails(el,e,today,compact=false){
  let lines;
  if(e.online)lines=['Online über Microsoft Teams',e.time||'Uhrzeit folgt',onlineRegistration(e.registration_url)?'Einmal anmelden, Teams-Link monatlich per E-Mail erhalten.':'Online-Anmeldung und Teams-Link folgen.'];
  else if(e.status==='planned'&&!e.venue)lines=['Ort und Uhrzeit noch offen.',e.price>0?'Der Ticketlink folgt.':'Details und Teilnahme folgen.'];
  else{
   lines=[e.venue||'Ort folgt',e.time||'Uhrzeit folgt'];
   if(!compact){
    if(e.address)lines.splice(1,0,e.address);
    if(e.capacity)lines.push('Kapazität: '+e.capacity+' Personen');
    lines.push(e.status==='cancelled'?'Dieses Treffen ist abgesagt.':booking(e,today)[1]?'Buchung über Eventfrog.':'Buchung noch nicht geöffnet.');
   }else if(e.status==='cancelled')lines.push('Dieses Treffen ist abgesagt.');
  }
  el.replaceChildren(...lines.flatMap((line,i)=>i?[document.createElement('br'),document.createTextNode(line)]:[document.createTextNode(line)]));
 }
 const selections=new WeakMap();
 const state=e=>e.status==='cancelled'?'abgesagt':e.status==='confirmed'?'bestätigt':'geplant';
 const priceLabel=e=>e.price===0?'kostenlos':Number.isFinite(e.price)?e.price+' € pro Person':'';
 function row(ev,today){
  const article=document.createElement('article'),head=document.createElement('div'),body=document.createElement('div'),t=document.createElement('time'),meta=document.createElement('p'),details=document.createElement('p'),button=document.createElement('button');
  article.className='event-row'+(ev.online?' event-row--online':'');details.className='event-details';
  t.dateTime=ev.date;t.textContent=short(ev.date)+ev.date.slice(0,4);
  meta.textContent=[ev.city,priceLabel(ev),state(ev)].filter(Boolean).join(' · ');
  head.append(t,meta);body.append(details,button);article.append(head,body);
  updateDetails(details,ev,today);
  if(ev.online){const url=onlineRegistration(ev.registration_url),control=document.createElement(url?'a':'button');control.className='ticket-button';control.textContent=url?'Link per E-Mail erhalten':'Online-Anmeldung folgt';if(url){control.href=url;control.target='_blank';control.rel='noopener noreferrer'}else{control.disabled=true;control.type='button'}button.replaceWith(control)}
  else updateButton(button,ev,today);
  return article;
 }
 function renderHero(view,events,index,today){
  const hero=view.querySelector('.event-hero')||document.querySelector('.home-event-layer .event-hero'),e=events[index];
  if(!hero||!e)return;
  selections.set(view,e.date);hero.dataset.eventIndex=String(index);
  hero.querySelector('h2').textContent=index===0?'Nächstes Präsenztreffen':'Weiteres Präsenztreffen';hero.setAttribute('aria-label',hero.querySelector('h2').textContent);
  const time=hero.querySelector('.event-date'),year=document.createElement('span');
  time.dateTime=e.date;year.textContent='Donnerstag · '+e.date.slice(0,4)+' · '+state(e);
  time.replaceChildren(document.createTextNode(short(e.date)),year);
  hero.querySelector('.event-place strong').textContent=e.city;
  const price=hero.querySelector('.event-place>span');
  if(Number.isFinite(e.price)){const per=document.createElement('small');per.textContent='pro Person';price.replaceChildren(document.createTextNode(e.price+' € '),per)}else price.textContent='Teilnahme folgt';
  hero.querySelector('.event-status').textContent=e.status==='planned'?'Treffen in Planung':booking(e,today)[0];
  updateDetails(hero.querySelector('.event-details'),e,today,true);updateButton(hero.querySelector('.ticket-button'),e,today);
  const nav=hero.querySelector('.event-switcher');nav.hidden=events.length<2;
  nav.querySelector('[data-event-step="-1"]').disabled=index===0;
  nav.querySelector('[data-event-step="1"]').disabled=index===events.length-1;
  const position=nav.querySelector('[data-event-position]');position.textContent=(index+1)+' / '+events.length;
  position.setAttribute('aria-label','Termin '+(index+1)+' von '+events.length+': '+short(e.date)+e.date.slice(0,4)+', '+state(e));
 }
 function refresh(){
  if(!global.KIWERK_EVENTS)return;
  const today=todayISO(),events=upcoming(global.KIWERK_EVENTS,today,4),e=events[0];if(!e)return;
  document.querySelectorAll('[data-event-view]').forEach(view=>{
   renderHero(view,events,Math.max(0,events.findIndex(ev=>ev.date===selections.get(view))),today);
   // Keep the first three dates visible; preserve later dates in an accessible disclosure.
   // This also upgrades an older cached static page that still has a flat list.
   const list=view.querySelector('.event-list');
   if(list){
    let upcoming=list.querySelector('.event-list__upcoming');
    let more=list.querySelector('.event-list__more');
    let additional=list.querySelector('.event-list__additional');
    if(!upcoming||!more||!additional){
     upcoming=document.createElement('div');upcoming.className='event-list__upcoming';
     more=document.createElement('details');more.className='event-list__more';
     const summary=document.createElement('summary');summary.textContent='Weitere Termine anzeigen';
     additional=document.createElement('div');additional.className='event-list__additional';
     more.append(summary,additional);
     const old=[...list.querySelectorAll('.event-row')],anchor=old[0]||list.querySelector('noscript');
     if(anchor)anchor.before(upcoming,more);else list.append(upcoming,more);
     old.forEach(item=>item.remove());
    }
    const entries=schedule(global.KIWERK_EVENTS,today,12).map(ev=>row(ev,today));
    upcoming.replaceChildren(...entries.slice(0,3));
    additional.replaceChildren(...entries.slice(3));
    more.hidden=entries.length<=3;
   }
  });
  document.querySelectorAll('[data-next-date]').forEach(node=>node.textContent=short(e.date)+e.date.slice(0,4));
  document.dispatchEvent(new Event('kiwerk:events'));
 }
 function selectEvent(event){
  const button=event.target.closest('[data-event-step]');if(!button||button.disabled)return;
  const view=button.closest('[data-event-view]');if(!view)return;
  const today=todayISO(),events=upcoming(global.KIWERK_EVENTS,today,4),index=events.findIndex(e=>e.date===selections.get(view));
  renderHero(view,events,Math.max(0,Math.min(events.length-1,index+Number(button.dataset.eventStep))),today);
  document.dispatchEvent(new Event('kiwerk:events'));
 }
 function layout(){document.documentElement.classList.add('events-ready');document.querySelectorAll(".event-mount").forEach(m=>{const h=m.querySelector(".event-hero");if(!h)return;const phone=matchMedia("(max-width:900px) and (orientation:portrait)").matches,w=phone?390:1280,height=phone?693.333333:720,scale=m.clientWidth/w;h.dataset.layout=phone?"portrait":"wide";h.style.width=w+"px";h.style.height=height+"px";h.style.transform=`scale(${scale})`;m.style.height=height*scale+"px"})} const api={upcoming,online,schedule,booking,todayISO};if(typeof module!=='undefined')module.exports=api;else{global.KiwerkEvents=api;document.addEventListener("click",selectEvent);refresh();layout();addEventListener("resize",layout,{passive:true});let day=todayISO();setInterval(()=>{if(day!==todayISO()){day=todayISO();refresh()}},60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()})}
})(typeof window==='undefined'?globalThis:window);
