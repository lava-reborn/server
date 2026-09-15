class lol.core.player.Lessor extends lol.core.player.NPC
{
   var give_transport;
   var transArray;
   static var staticID = "Lessor";
   static var RTYPE = 6;
   function Lessor(ID)
   {
      super(ID);
   }
   function userInfo(obj)
   {
      super.userInfo(obj);
      this.give_transport = obj.param.give_transport;
      this.createTransList(this.give_transport);
   }
   function createTransList(give_transport)
   {
      this.transArray = new Array();
      var _loc3_;
      var _loc2_;
      for(var _loc5_ in give_transport)
      {
         _loc3_ = give_transport[_loc5_];
         _loc2_ = lol.core.transport.TransportFactory.create(_loc3_);
         this.transArray.push(_loc2_);
      }
   }
}
