class lol.core.globmap.MapObject
{
   var cl;
   var dispatchEvent;
   var id;
   var interval;
   var liveInterval;
   var liveTimer;
   var moveTime;
   var spt;
   var spt_int;
   var startTime;
   var vx;
   var vy;
   var x;
   var x0;
   var y;
   var y0;
   var moveTimer = 100;
   function MapObject(ID, X, Y)
   {
      this.id = ID;
      this.x = Number(X);
      this.y = Number(Y);
      lol.events.LEventDispatcher.initialize(this);
      this.startPC();
   }
   function startMove(VX, VY, T)
   {
      clearInterval(this.interval);
      this.liveTimer = 0;
      this.moveTime = 0;
      this.x0 = this.x;
      this.y0 = this.y;
      this.vx = VX;
      this.vy = VY;
      this.startTime = getTimer();
      this.interval = setInterval(this,"moveDirectionCalc",this.moveTimer);
      this.dispatchEvent({type:"startMove"});
   }
   function moveDirectionCalc()
   {
      var _loc2_ = getTimer();
      this.moveTime = _loc2_ - this.startTime;
      var _loc4_ = this.x;
      var _loc3_ = this.y;
      this.x = this.x0 + this.moveTime * this.vx / 1000;
      this.y = this.y0 + this.moveTime * this.vy / 1000;
      this.dispatchEvent({type:"position",x:this.x,y:this.y,time:_loc2_});
      if(_loc4_ == this.x && _loc3_ == this.y)
      {
         clearInterval(this.interval);
         this.dispatchEvent({type:"stopMove"});
      }
   }
   function startCheckLive()
   {
      this.liveTimer = 0;
      this.liveInterval = setInterval(this,"checkLive",1000);
   }
   function checkLive()
   {
      this.liveTimer = this.liveTimer + 1;
      if(this.liveTimer > 3)
      {
         if(!this.cl)
         {
            this.cl = true;
            this.dispatchEvent({type:"faraway"});
         }
      }
      else if(this.cl)
      {
         this.cl = false;
         this.dispatchEvent({type:"near"});
      }
      if(this.liveTimer > 6)
      {
         clearInterval(this.interval);
         this.dispatchEvent({type:"stopMove"});
         clearInterval(this.liveInterval);
         this.dispatchEvent({type:"lost"});
      }
   }
   function moveDirectionInc()
   {
      var _loc2_ = getTimer();
      var _loc3_ = _loc2_ - this.startTime - this.moveTime;
      this.moveTime = _loc2_ - this.startTime;
      this.x += this.vx * _loc3_ / 1000;
      this.y += this.vy * _loc3_ / 1000;
      this.dispatchEvent({type:"position",x:this.x,y:this.y,time:_loc2_});
   }
   function kill()
   {
      clearInterval(this.interval);
      clearInterval(this.liveInterval);
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("MapObject_" + this.id + "_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
