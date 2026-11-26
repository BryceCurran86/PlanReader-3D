/** Stable object dwell, not a timer-based selection or edit. Closing a palette
 * suppresses the same target until the pointer leaves it. */
export class HoverToolDwell {
 private key:string|null=null;
 private since=0;
 private blocked:string|null=null;
 private fired=false;
 private readonly delayMs:number;
 constructor(delayMs=450){this.delayMs=delayMs;}
 observe(key:string|null,now:number):boolean{
  if(!Number.isFinite(now))return false;
  if(key!==this.key){this.key=key;this.since=now;this.fired=false;if(key!==this.blocked)this.blocked=null;return false;}
  if(!key||key===this.blocked||this.fired||now-this.since<this.delayMs)return false;
  this.fired=true;return true;
 }
 dismiss(key:string|null){this.key=key;this.blocked=key;this.fired=true;}
 reset(){this.key=null;this.since=0;this.blocked=null;this.fired=false;}
}
