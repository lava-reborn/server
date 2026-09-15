class lol.core.player.BankAccount
{
   var XMC;
   var dispatchEvent;
   function BankAccount()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
   }
   function convertGoldToAfro(num)
   {
      var _loc3_;
      if(num && !isNaN(num))
      {
         _loc3_ = new lol.server.mess.CSM_BA_ConvertAfroToGold(num);
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.converAck);
         }
      }
   }
   function converAck(obj)
   {
      var _loc2_;
      if(obj.param.res == 0)
      {
         _loc2_ = true;
      }
      else
      {
         _loc2_ = false;
      }
      this.dispatchEvent({type:"converted",success:_loc2_});
   }
}
