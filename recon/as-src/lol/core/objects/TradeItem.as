class lol.core.objects.TradeItem extends lol.core.objects.P_Item
{
   var dispatchEvent;
   var tradeID;
   function TradeItem(tID, typeID)
   {
      super();
      this.item = new lol.core.objects.Item("model" + tID,typeID,0);
      this.tradeID = tID;
      this.create(typeID);
   }
   function create(typeID)
   {
      var _loc2_ = lol.core.objects.ItemFactory.createPrototype(typeID);
      if(_loc2_.inited)
      {
         this.itemUpdate();
      }
      else
      {
         _loc2_.addEventListener("itemUpdate",this);
      }
   }
   function itemUpdate(obj)
   {
      var _loc2_ = lol.core.objects.ItemFactory.createPrototype(this.typeID);
      var _loc3_ = lol.core.objects.ItemFactory.getClass(_loc2_.rootID);
      this.item = new _loc3_(this.tradeID + 1,_loc2_.typeID,_loc2_.rootID);
      this.initParams();
      this.dispatchEvent({type:"itemUpdate"});
   }
   function initParams()
   {
      if(this.item instanceof lol.core.objects.Heapable)
      {
         lol.core.objects.Heapable(this.item).size = this.item.getProp("max_count");
      }
   }
}
