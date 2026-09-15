class lol.core.player.Resurrector
{
   var XMC;
   var dispatchEvent;
   var resurrectPan;
   function Resurrector()
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("lch",this);
      lol.events.LEventDispatcher.initialize(this);
   }
   function resurrectGamer()
   {
      var _loc2_ = lol.core.Master.getInstance();
      var _loc3_ = _loc2_.gamer;
      _loc2_.currentState = lol.core.Master.DEAD_STATE;
      this.resurrectPan = lol.core.SceneShifter.openNewWindow("regeneration").content;
   }
   function resurrect(res_type)
   {
      var _loc2_ = new lol.server.mess.CSM_Resurrect(Number(res_type));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.resurrectAck);
      }
   }
   function resurrectAck(obj)
   {
      trace("ressurectAck");
      var _loc4_ = obj.param.res;
      var _loc5_ = false;
      var _loc2_;
      var _loc3_;
      if(_loc4_ == 0)
      {
         lol.core.SceneShifter.closeWindow("regeneration");
         this.resurrectPan = null;
         _loc2_ = lol.core.Master.getInstance();
         _loc3_ = _loc2_.gamer;
         _loc3_.playerInfo.dead = false;
         _loc2_.currentState = lol.core.Master.LOCAL_STATE;
         _loc5_ = true;
      }
      this.dispatchEvent({type:"resurrect",success:_loc5_});
   }
   function lch(obj)
   {
      var _loc2_ = obj.param.dead;
      var _loc3_;
      if(_loc2_ != undefined)
      {
         _loc3_ = _loc2_;
         if(_loc3_ == lol.core.player.Gamer.ID)
         {
            this.resurrectGamer();
         }
      }
   }
}
