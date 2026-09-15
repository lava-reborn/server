class lol.core.player.Player extends lol.core.player.Entity
{
   var XMC;
   var dispatchEvent;
   var equipment;
   var highLight;
   var id;
   static var staticID = "Player";
   var _prepare = 0;
   var _premium = 0;
   function Player(ID)
   {
      super(ID);
      if(this.id != lol.core.player.Gamer.ID && lol.core.Master.getInstance().currentState == lol.core.Master.LOCAL_STATE)
      {
         this.equipment.getStuff(3,this.id);
      }
   }
   function requestInfo()
   {
      var _loc2_ = this.id != lol.core.player.Gamer.ID ? this.id : 0;
      var _loc3_ = new lol.server.mess.CSM_P_GetInfo(0,_loc2_,0);
      this.XMC.Send(_loc3_);
   }
   function userInfo(obj)
   {
      this.highLight = !obj.param.hl ? 0 : obj.param.hl;
      this.premium = !obj.param.pr ? 0 : obj.param.pr;
      super.userInfo(obj);
   }
   function set prepare(value)
   {
      this._prepare = !value ? 0 : value - 2;
      this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.PREPARE,this));
   }
   function get prepare()
   {
      return this._prepare;
   }
   function set premium(value)
   {
      this._premium = !value ? 0 : value;
   }
   function get premium()
   {
      return this._premium;
   }
}
