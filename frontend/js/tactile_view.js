const STOPS=[[0,112,179,220],[.45,71,191,200],[.7,240,196,91],[.86,238,144,67],[1,211,83,83]];
// Visual slot -> incoming sensor index. A live press test showed that the
// left glove's physical wrist row arrives as F16..F23, while the artwork's
// wrist row was reading F40..F47. Keep this correction left-only.
const LEFT_VISUAL_SOURCE=Array.from({length:68},(_,i)=>i);
for(let offset=0;offset<8;offset++){
  LEFT_VISUAL_SOURCE[36+offset]=60+offset;
  LEFT_VISUAL_SOURCE[60+offset]=36+offset;
}
const sourceIndexFor=(side,visualIndex)=>side==='left'?LEFT_VISUAL_SOURCE[visualIndex]:visualIndex;
function color(v,a=1){v=Math.max(0,Math.min(1,v));let hi=1;while(hi<STOPS.length-1&&v>STOPS[hi][0])hi++;const x=STOPS[hi-1],y=STOPS[hi],t=(v-x[0])/(y[0]-x[0]);return `rgba(${x[1]+(y[1]-x[1])*t},${x[2]+(y[2]-x[2])*t},${x[3]+(y[3]-x[3])*t},${a})`}
export class TactileView {
  constructor(card, layout, imageUrl) {
    this.card=card;this.side=card.dataset.side;this.canvas=card.querySelector('canvas');this.ctx=this.canvas.getContext('2d');this.layout=layout;this.data=null;this.mode='smooth';this.showValues=false;this.showIds=false;this.image=card.querySelector('.tactile-hand-image');if(imageUrl)this.image.src=imageUrl;this.image.addEventListener('load',()=>this.draw());
    this.observer=new ResizeObserver(()=>this.draw());this.observer.observe(this.canvas.parentElement);
  }
  setOptions(options){Object.assign(this,options);this.draw()}
  update(data){this.data=data;this.card.querySelector('.data-pill').textContent='LIVE';this.card.querySelector('.data-pill').className='data-pill live';['maximum','average','contact_count','high_count'].forEach(key=>this.card.querySelector(`[data-stat="${key}"]`).textContent=Number(data[key]||0).toFixed(key.includes('count')?0:2));this.draw()}
  timeout(){const pill=this.card.querySelector('.data-pill');pill.textContent='TIMEOUT';pill.className='data-pill timeout'}
  draw(){
    const box=this.canvas.parentElement.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);
    const w=Math.max(1,Math.round(box.width*d)),h=Math.max(1,Math.round(box.height*d));
    if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h}
    const ctx=this.ctx;ctx.setTransform(d,0,0,d,0,0);
    const cw=box.width,ch=box.height;ctx.clearRect(0,0,cw,ch);
    // This canvas exactly overlays the fixed 920:1040 image stage, matching
    // live_tactile_68_modbus_web.py -> live_tactile_68_web.py.
    if(!this.data)return;
    let values;
    if(this.mode==='raw'){
      values=this.data.raw||[];
      const lo=Math.min(...values),hi=Math.max(lo+1,...values);
      values=values.map(v=>(v-lo)/(hi-lo)*100);
    }else values=this.data.display||[];
    const size=Math.min(cw,ch);
    for(let i=0;i<68;i++){
      const p=this.layout.points[i];
      // Mirror both the right artwork (CSS) and its point coordinate so the
      // physical thumb-side remains the visual thumb-side.
      const x=(this.side==='right'?1-p[0]:p[0])*cw,y=p[1]*ch;
      const sourceIndex=sourceIndexFor(this.side,i);
      const v=Math.max(0,Math.min(1,(values[sourceIndex]||0)/100)),r=4+v*size*.045;
      if(v>0){
        const g=ctx.createRadialGradient(x,y,0,x,y,r);
        g.addColorStop(0,color(v,.95));g.addColorStop(.4,color(v,.42));g.addColorStop(1,color(v,0));
        ctx.fillStyle=g;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
        ctx.fillStyle=color(Math.min(1,v+.15),1);ctx.beginPath();ctx.arc(x,y,2+v*2.5,0,Math.PI*2);ctx.fill();
      }
      if(this.showIds||this.showValues){
        ctx.font='9px ui-monospace';ctx.fillStyle='#244d68';
        const text=[this.showIds?this.layout.names[sourceIndex]:'',this.showValues?Number((this.mode==='raw'?this.data.raw[sourceIndex]:this.data.smoothed[sourceIndex])||0).toFixed(1):''].filter(Boolean).join(' ');
        ctx.fillText(text,x+5,y-4);
      }
    }
  }
}

export class TactileHistory {
  constructor(canvas,max=300){this.canvas=canvas;this.ctx=canvas.getContext('2d');this.max=max;this.rows={left:[],right:[]};new ResizeObserver(()=>this.draw()).observe(canvas)}
  push(side,data){const row={max:Number(data.maximum||0),avg:Number(data.average||0)};this.rows[side].push(row);if(this.rows[side].length>this.max)this.rows[side].shift();this.draw()}
  draw(){const r=this.canvas.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);if(this.canvas.width!==Math.round(r.width*d)||this.canvas.height!==Math.round(r.height*d)){this.canvas.width=Math.round(r.width*d);this.canvas.height=Math.round(r.height*d)}const c=this.ctx;c.setTransform(d,0,0,d,0,0);c.clearRect(0,0,r.width,r.height);c.strokeStyle='#e3edf4';for(let i=1;i<4;i++){c.beginPath();c.moveTo(0,r.height*i/4);c.lineTo(r.width,r.height*i/4);c.stroke()}const vals=[...this.rows.left,...this.rows.right],mx=Math.max(8,...vals.map(x=>x.max));const line=(rows,key,color)=>{if(rows.length<2)return;c.beginPath();rows.forEach((v,i)=>{const x=i*r.width/(this.max-1),y=r.height-5-(v[key]/mx)*(r.height-10);i?c.lineTo(x,y):c.moveTo(x,y)});c.strokeStyle=color;c.lineWidth=1.7;c.stroke()};line(this.rows.left,'max','#397fbd');line(this.rows.right,'max','#d9895f');line(this.rows.left,'avg','#55a7ab');line(this.rows.right,'avg','#a786c4')}
}
