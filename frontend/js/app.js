import { LiveSocket } from './websocket.js';
import { Navigation } from './navigation.js';
import { RGBView } from './rgb_view.js?v=20260713d';
import { TactileView, TactileHistory } from './tactile_view.js?v=20260714c';
import { HandView, HandFallbackView } from './hand_view.js?v=20260714a';
import { AcquisitionView } from './acquisition_view.js';

const page=document.body.dataset.page;
const setStatus=(id,text,kind='waiting')=>{const el=document.querySelector(id);if(el){el.textContent=text;el.className=`status-text ${kind}`}};

async function landing(){
  const capabilities=channels=>{
    const available=[];
    if(channels?.rgb?.connected)available.push("第一视角画面");
    if(channels?.tactile_left?.connected||channels?.tactile_right?.connected)available.push("双手触觉");
    if(channels?.hand_pose_left?.connected||channels?.hand_pose_right?.connected)available.push("三维手部姿态");
    document.querySelector("#landing-sources").textContent=available.join(" · ")||"等待实时数据接入";
  };
  try{
    const status=await fetch("/api/status").then(response=>response.json());
    setStatus("#landing-backend","在线","ok");
    document.querySelector("#landing-mode").textContent=status.mode==="mock"?"演示模式":"实时模式";
    const ready=status.mode==="mock"||status.ros?.initialized;
    setStatus("#landing-ros",ready?"已就绪":"等待接入",ready?"ok":"waiting");
    capabilities(status.channels);
  }catch(error){
    setStatus("#landing-backend","离线","error");
    setStatus("#landing-ros","等待接入","waiting");
  }
  const socket=new LiveSocket(null,{
    state:state=>setStatus("#landing-ws",state==="open"?"已连接":state==="connecting"?"连接中":"已断开",state==="open"?"ok":state==="closed"?"error":"waiting"),
    message:message=>{
      if(message.type!=="system_status")return;
      const channels=message.channels||{};
      setStatus("#landing-rgb",channels.rgb?.connected?"画面正常":channels.rgb?.timed_out?"等待画面":"未连接",channels.rgb?.connected?"ok":"waiting");
      const hand=channels.hand_pose_left?.connected||channels.hand_pose_right?.connected;
      setStatus("#landing-hand",hand?"数据正常":"等待数据",hand?"ok":"waiting");
      capabilities(channels);
    }
  });
  socket.connect();
  addEventListener("beforeunload",()=>socket.close());
}

async function dashboard(){window.APP_CONFIG=await fetch('/api/config').then(r=>r.json());const layout=await fetch('/api/tactile/layout').then(r=>r.json());const cards={rgb:document.querySelector('#rgb-card'),left:document.querySelector('#tactile-left-card'),right:document.querySelector('#tactile-right-card'),hand:document.querySelector('#hand-card')};const rgb=new RGBView(cards.rgb),tactile={left:new TactileView(cards.left,layout,'/static/assets/hand_live.png'),right:new TactileView(cards.right,layout,'/static/assets/hand_live.png')},history=new TactileHistory(document.querySelector('#tactile-history'));let jointSide='left',jointData={left:[],right:[]};const renderAngles=()=>{const groups={};for(const row of jointData[jointSide]||[])(groups[row.finger]??=[]).push(row);document.querySelector('#joint-angle-list').innerHTML=Object.entries(groups).map(([finger,rows])=>`<section class="finger-angle-group"><h3>${finger}</h3>${rows.map(r=>`<div class="angle-row ${r.valid?'':'invalid'}"><span>${r.joint}</span><i style="--angle:${Math.min(100,Math.abs(r.degrees)/130*100)}%"></i><b>${r.valid?Number(r.degrees).toFixed(1)+'°':'--'}</b></div>`).join('')}</section>`).join('')};const onAngles=(side,angles)=>{jointData[side]=angles;if(side===jointSide)renderAngles()};let hand;try{hand=new HandView(cards.hand,onAngles)}catch(error){console.warn('WebGL unavailable, using Canvas FK fallback',error);hand=new HandFallbackView(cards.hand,onAngles,error)}document.querySelector('#joint-side').addEventListener('change',e=>{jointSide=e.target.value;renderAngles()});const acquisition=new AcquisitionView(document.querySelector('#acquisition-card'));
  const move=view=>{const staging=document.querySelector('#component-staging');if(view==='overview'){document.querySelector('#overview-rgb-slot').append(cards.rgb);document.querySelector('#overview-tactile-slot').append(cards.left,cards.right);document.querySelector('#overview-hand-slot').append(cards.hand)}else if(view==='tactile'){document.querySelector('#tactile-full-slot').append(cards.left,cards.right);staging.append(cards.rgb,cards.hand)}else if(view==='hand'){document.querySelector('#hand-main-slot').append(cards.hand);staging.append(cards.rgb,cards.left,cards.right)}else staging.append(cards.rgb,cards.left,cards.right,cards.hand);requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')))};const navigation=new Navigation(move);const requestedView=new URLSearchParams(location.search).get('view');navigation.show(['overview','tactile','hand'].includes(requestedView)?requestedView:'overview');
  const options={mode:'smooth',showValues:false,showIds:false};document.querySelectorAll('[data-tactile-mode]').forEach(b=>b.addEventListener('click',()=>{options.mode=b.dataset.tactileMode;document.querySelectorAll('[data-tactile-mode]').forEach(x=>x.classList.toggle('active',x===b));Object.values(tactile).forEach(v=>v.setOptions(options))}));document.querySelector('#toggle-tactile-values').addEventListener('click',e=>{options.showValues=!options.showValues;e.currentTarget.classList.toggle('active',options.showValues);Object.values(tactile).forEach(v=>v.setOptions(options))});document.querySelector('#toggle-tactile-ids').addEventListener('click',e=>{options.showIds=!options.showIds;e.currentTarget.classList.toggle('active',options.showIds);Object.values(tactile).forEach(v=>v.setOptions(options))});document.querySelector('#toggle-tactile-range').addEventListener('click',e=>e.currentTarget.classList.toggle('active'));
  const chips={ws:document.querySelector('#chip-ws'),rgb:document.querySelector('#chip-rgb')};let receivedRGB=false;const socket=new LiveSocket(null,{state:s=>{chips.ws.classList.toggle('online',s==='open');chips.ws.classList.toggle('timeout',s==='closed')},message:m=>{if(m.type==='rgb'){receivedRGB=true;rgb.update(m.data)}else if(m.type==='tactile_left'||m.type==='tactile_right'){const side=m.type.endsWith('left')?'left':'right';tactile[side].update(m.data);history.push(side,m.data);hand.updateTactile(side,m.data)}else if(m.type==='hand_pose_left'||m.type==='hand_pose_right'){hand.update(m.type.endsWith('left')?'left':'right',m.data)}else if(m.type==='system_status'){chips.rgb.classList.toggle('online',m.channels?.rgb?.connected);chips.rgb.classList.toggle('timeout',m.channels?.rgb?.timed_out);rgb.setTimedOut(m.channels?.rgb?.timed_out,receivedRGB);if(m.channels?.tactile_left?.timed_out)tactile.left.timeout();if(m.channels?.tactile_right?.timed_out)tactile.right.timeout()}else if(m.type==='acquisition_status')acquisition.update(m.data)}});socket.connect();setInterval(()=>document.querySelector('#clock').textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false}),500);addEventListener('beforeunload',()=>{socket.close();hand.dispose()})}

if(page==='landing')landing();else dashboard();
