const fmtTime = value => value ? new Date(value * 1000).toLocaleTimeString('zh-CN', {hour12:false}) : '--';
export class RGBView {
  constructor(card) {
    this.card = card; this.image = card.querySelector('#rgb-image'); this.empty = card.querySelector('#rgb-empty'); this.frame = card.querySelector('#rgb-frame');
    this.heading = card.querySelector('.card-heading'); this.metrics = card.querySelector('.metric-strip');
    this.sourceWidth = 16; this.sourceHeight = 9;
    this.pending = null; this.loading = false; this.raf = 0; this.displayed = null; this.renderTimes = [];
    this.image.addEventListener('load', () => this.onImageLoaded());
    this.image.addEventListener('error', () => { this.loading=false; this.schedule(); });
    card.querySelector('#rgb-fullscreen').addEventListener('click', () => this.frame.requestFullscreen?.());
    this.resizeObserver = new ResizeObserver(() => this.fitFrame());
    this.resizeObserver.observe(card);
    document.addEventListener('fullscreenchange', () => this.fitFrame());
  }
  update(data) {
    // Keep only the newest frame. Never start another JPEG decode until the
    // current image has completed, otherwise browsers visibly lag while
    // decoding frames that will never be shown.
    if (data.jpeg) { this.pending=data; this.schedule(); }
    this.card.querySelector('#rgb-resolution').textContent = data.width ? `${data.width} × ${data.height}` : '--';
    if (data.width > 0 && data.height > 0 &&
        (data.width !== this.sourceWidth || data.height !== this.sourceHeight)) {
      this.sourceWidth = data.width;
      this.sourceHeight = data.height;
      this.fitFrame();
    }
    this.card.querySelector('#rgb-last').textContent = fmtTime(data.received_at);
  }
  fitFrame() {
    if (document.fullscreenElement === this.frame) {
      this.frame.style.removeProperty('width');
      this.frame.style.removeProperty('height');
      return;
    }
    const cardStyle = getComputedStyle(this.card);
    const horizontalPadding = parseFloat(cardStyle.paddingLeft) + parseFloat(cardStyle.paddingRight);
    const verticalPadding = parseFloat(cardStyle.paddingTop) + parseFloat(cardStyle.paddingBottom);
    const rowGap = parseFloat(cardStyle.rowGap) || 0;
    const availableWidth = Math.max(0, this.card.clientWidth - horizontalPadding);
    const availableHeight = Math.max(0, this.card.clientHeight - verticalPadding -
      (this.heading?.offsetHeight || 0) - (this.metrics?.offsetHeight || 0) - rowGap * 2);
    if (!availableWidth || !availableHeight) return;
    const aspect = this.sourceWidth / this.sourceHeight;
    const width = Math.min(availableWidth, availableHeight * aspect);
    this.frame.style.width = `${Math.floor(width)}px`;
    this.frame.style.height = `${Math.floor(width / aspect)}px`;
    this.frame.style.setProperty('--rgb-aspect', `${this.sourceWidth} / ${this.sourceHeight}`);
  }
  schedule() {
    if(this.loading||this.raf||!this.pending)return;
    this.raf=requestAnimationFrame(()=>{this.raf=0;this.commitLatest()});
  }
  commitLatest() {
    if(this.loading||!this.pending)return;
    this.displayed=this.pending;this.pending=null;this.loading=true;
    this.image.src=`data:${this.displayed.mime||'image/jpeg'};base64,${this.displayed.jpeg}`;
  }
  onImageLoaded() {
    const data=this.displayed,now=performance.now();this.loading=false;this.empty.classList.add('hidden');
    this.renderTimes.push(now);while(this.renderTimes.length&&now-this.renderTimes[0]>1000)this.renderTimes.shift();
    const visualHz=this.renderTimes.length>1?(this.renderTimes.length-1)/Math.max(.001,(this.renderTimes.at(-1)-this.renderTimes[0])/1000):0;
    this.card.querySelector('#rgb-fps').textContent=`${visualHz.toFixed(1)} / ${Number(data?.hz||0).toFixed(1)} Hz`;
    this.schedule();
  }
  setTimedOut(timedOut, everReceived) {
    if (!timedOut) return;
    this.empty.textContent = everReceived ? 'RGB 数据已超时' : '等待图像数据'; this.empty.classList.remove('hidden');
  }
}
