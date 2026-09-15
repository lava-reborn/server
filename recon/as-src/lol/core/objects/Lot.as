class lol.core.objects.Lot
{
   var dispatchEvent;
   var item;
   static var LOT_UPDATE = lol.core.objects.Lot.LOT_UPDATE;
   function Lot()
   {
      lol.events.LEventDispatcher.initialize(this);
   }
   function kill()
   {
      this.item.removeEventListener("itemUpdate",this,this.itemUpdate);
   }
   function setItem(oID)
   {
      this.item = lol.core.objects.Item(lol.core.objects.ItemFactory.create(oID,true));
      this.item.addEventListener("itemUpdate",this,this.itemUpdate);
   }
   function itemUpdate()
   {
      this.dispatchEvent({type:lol.core.objects.Lot.LOT_UPDATE});
   }
   function get name()
   {
      var _loc2_;
      if(this.item instanceof lol.core.objects.Ammo)
      {
         if(this.item.getProp("name") != undefined)
         {
            _loc2_ = this.item.getProp("name") + " " + this.item.getProp("mod_type");
         }
         else
         {
            _loc2_ = "ЗАГРУЖАЕТСЯ";
         }
      }
      else
      {
         _loc2_ = !this.item.getProp("name") ? "ЗАГРУЖАЕТСЯ" : this.item.getProp("name");
      }
      return _loc2_;
   }
   function get count()
   {
      var _loc2_ = !(this.item instanceof lol.core.objects.Heapable) ? 1 : this.item.getProp("size");
      return _loc2_;
   }
}
