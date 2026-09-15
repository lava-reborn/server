class lol.core.player.APManager
{
   var XMC;
   var _maxAP;
   var currentAP;
   var dAP;
   var dispatchEvent;
   var dtAPInterval;
   var wState;
   var dt = 600;
   var incT = 0;
   var moveAP = 1;
   function APManager()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("c_ap",this,this.syncAPtoServer);
   }
   function syncAPtoServer(obj)
   {
      this.ap = obj.param.ap;
   }
   function warState(ws)
   {
      this.wState = ws;
      if(ws == 1)
      {
         lol.core.Master.getInstance().gamer.walker.addEventListener("finishPart",this,this.gamerMove);
         this.ap = this.maxAP;
         this.calcAP(true);
      }
      else
      {
         lol.core.Master.getInstance().gamer.walker.removeEventListener("finishPart",this,this.gamerMove);
         this.ap = this.maxAP;
         this.calcAP(false);
      }
   }
   function setAP(dap, apmax)
   {
      var _loc2_ = lol.core.Master.getInstance().currentLocation.warStatus;
      this.warState(_loc2_);
      this.dAP = dap;
      this._maxAP = apmax;
   }
   function calcAP(flag)
   {
      clearInterval(this.dtAPInterval);
      if(flag)
      {
         this.dtAPInterval = setInterval(this,"incAP",this.dt);
      }
   }
   function incAP()
   {
      var _loc2_ = getTimer() - this.incT;
      this.ap += this.dAP;
      this.incT = getTimer();
   }
   function set ap(a)
   {
      this.currentAP = a;
      if(this.currentAP < 0)
      {
         this.currentAP = 0;
         this.dispatchEvent({type:"breakAction"});
      }
      if(this.currentAP > this.maxAP)
      {
         this.currentAP = this.maxAP;
      }
      this.dispatchEvent({type:"actionPoints"});
   }
   function get ap()
   {
      return this.currentAP;
   }
   function get maxAP()
   {
      return this._maxAP;
   }
   function kill()
   {
      this.calcAP(false);
   }
   function gamerMove()
   {
      this.ap -= this.moveAP;
   }
   function syncAP(k)
   {
      this.ap += k * this.moveAP;
   }
}
