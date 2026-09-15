class lol.core.player.Upgrader extends lol.core.player.NPC
{
   var equipment;
   var neededItems;
   var upgradeCosts;
   var upgradedItems;
   static var staticID = "Upgrader";
   static var RTYPE = 3;
   function Upgrader(ID)
   {
      super(ID);
   }
   function userInfo(obj)
   {
      super.userInfo(obj);
      this.neededItems = obj.param.in_types;
      this.upgradeCosts = obj.param.costs;
      this.createUpgradeList(obj.param.out_types);
   }
   function createUpgradeList(arr)
   {
      this.upgradedItems = new Array();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < arr.length)
      {
         _loc3_ = arr[_loc2_];
         this.upgradedItems.push(_loc3_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function createAllUpgradeItems()
   {
      var _loc7_ = lol.core.Master.getInstance().gamer;
      var _loc8_ = _loc7_.equipment.bag;
      var _loc4_ = new Array();
      var _loc6_ = _loc8_.getItems();
      var _loc3_ = 0;
      var _loc5_;
      var _loc2_;
      while(_loc3_ < _loc6_.length)
      {
         _loc5_ = _loc6_[_loc3_];
         _loc2_ = 0;
         while(_loc2_ < this.neededItems.length)
         {
            if(_loc5_.typeID == this.neededItems[_loc2_])
            {
               _loc4_.push(_loc2_);
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc3_ = _loc3_ + 1;
      }
      _loc3_ = 0;
      while(_loc3_ < _loc4_.length)
      {
         this.createUpgradeItem(_loc4_[_loc3_],this.upgradedItems[_loc4_[_loc3_]]);
         _loc3_ = _loc3_ + 1;
      }
   }
   function createUpgradeItem(i, typeID)
   {
      var _loc2_ = new lol.core.objects.TradeItem(i,typeID);
      this.equipment.addItem(this.equipment.bag,_loc2_,undefined,false);
      var _loc3_ = lol.core.objects.ItemFactory.createPrototype(typeID);
      if(_loc3_.inited == true)
      {
         trace("createUpgradeItem upgradeCosts[upgradeItem.tradeID] = " + this.upgradeCosts[_loc2_.tradeID]);
         _loc2_.item.cost = this.upgradeCosts[_loc2_.tradeID];
      }
      else
      {
         _loc3_.addEventListener("itemUpdate",this);
      }
   }
   function __itemUpdate(obj)
   {
      var _loc3_ = obj.target;
      var _loc4_ = _loc3_.typeID;
      var _loc2_ = this.equipment.bag.getItemsByType(_loc4_)[0];
      _loc2_.item.cost = this.upgradeCosts[_loc2_.tradeID];
   }
   function itemUpdate(obj)
   {
      var _loc2_ = new lol.utils.Timeout(this,this.__itemUpdate,1000,obj);
   }
}
