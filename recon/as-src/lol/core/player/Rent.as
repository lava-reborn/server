class lol.core.player.Rent
{
   var XMC;
   var dispatchEvent;
   var lessorID;
   var master;
   function Rent(visavisID)
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.master = lol.core.Master.getInstance();
      var _loc2_ = this.master.gamer;
   }
   function ss_propose(id)
   {
      this.lessorID = id;
      lol.core.player.NPCService.openService(id);
   }
   function getTransport(typeID, day)
   {
      var _loc2_ = new lol.server.mess.CSM_TS_on_conv(this.lessorID,typeID,day);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getTransportAck);
      }
   }
   function getTransportAck(obj)
   {
      var _loc2_ = obj.param.res;
      if(_loc2_)
      {
         this.dispatchEvent({type:lol.core.transport.TransEvent.GET_TRANSPORT_FAIL});
      }
      else
      {
         this.dispatchEvent({type:lol.core.transport.TransEvent.GET_TRANSPORT_SUCCESS});
      }
   }
   function close()
   {
      this.kill();
   }
   function kill()
   {
      var _loc2_ = this.master.gamer;
      _loc2_.training = null;
   }
}
