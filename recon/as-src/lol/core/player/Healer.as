class lol.core.player.Healer extends lol.core.player.NPC
{
   var a_price;
   var g_price;
   var id;
   var supportList;
   static var staticID = "Healer";
   static var RTYPE = 5;
   function Healer(ID)
   {
      super(ID);
   }
   function userInfo(obj)
   {
      super.userInfo(obj);
      this.a_price = new lol.data.Money(obj.param.a_price,lol.data.Money.AFRO);
      this.g_price = new lol.data.Money(obj.param.a_price,lol.data.Money.GOLD);
      var _loc4_ = new lol.core.player.Attendance(lol.core.player.Attendance.HEAL,this.id);
      this.supportList.push(_loc4_);
   }
   function getMedPrice()
   {
      var _loc2_;
      if(this.a_price.moneyValue != undefined)
      {
         _loc2_ = this.a_price;
      }
      else if(this.g_price != undefined)
      {
         _loc2_ = this.g_price;
      }
      return _loc2_;
   }
}
