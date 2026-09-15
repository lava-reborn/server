class lol.core.player.Trader extends lol.core.player.NPC
{
   var SellListLoaded;
   var bg_NeedReputation;
   var bg_ObjectList;
   var equipment;
   var pmod;
   var rmod;
   var sellList;
   var smod;
   var type_list;
   static var staticID = "Trader";
   static var RTYPE = 1;
   function Trader(ID)
   {
      super(ID);
      this.SellListLoaded = false;
   }
   function userInfo(obj)
   {
      super.userInfo(obj);
      this.type_list = obj.param.type_list;
      this.bg_ObjectList = obj.param.bg_objects;
      this.bg_NeedReputation = obj.param.bg_obj_rep_req;
      this.pmod = obj.param.pmod;
      this.smod = obj.param.smod;
      this.rmod = obj.param.rmod;
   }
   function createSellList(arr)
   {
      if(this.sellList == undefined)
      {
         this.sellList = new Array();
      }
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < arr.length)
      {
         _loc3_ = arr[_loc2_];
         this.sellList.push(_loc3_);
         _loc4_ = new lol.core.objects.TradeItem(_loc2_,_loc3_);
         this.equipment.addItem(this.equipment.bag,_loc4_);
         _loc2_ = _loc2_ + 1;
      }
      this.SellListLoaded = true;
   }
   function createBGSellList(arr)
   {
      if(this.sellList == undefined)
      {
         this.sellList = new Array();
      }
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < arr.length)
      {
         _loc3_ = arr[_loc2_];
         this.sellList.push(_loc3_);
         _loc4_ = new lol.core.objects.TradeItem(_loc2_,_loc3_);
         this.equipment.addItem(this.equipment.bag,_loc4_);
         _loc2_ = _loc2_ + 1;
      }
      this.SellListLoaded = true;
   }
   function loadSellList()
   {
      this.createSellList(this.type_list);
   }
   function loadBGSellList()
   {
      this.createBGSellList(this.bg_ObjectList);
   }
}
