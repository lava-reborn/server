class lol.core.player.Bag
{
   var id;
   var itemList;
   var type = "all";
   function Bag(ID)
   {
      this.id = ID;
      this.itemList = new Array();
   }
   function addItem(_item, pos)
   {
      if(this.chekExist(_item) == true)
      {
         return null;
      }
      if(pos != undefined)
      {
         this.itemList.splice(pos,0,_item);
      }
      else
      {
         this.itemList.push(_item);
      }
      return _item;
   }
   function chekExist(_item)
   {
      for(var _loc2_ in this.itemList)
      {
         if(this.itemList[_loc2_].id == _item.id)
         {
            return true;
         }
      }
      return false;
   }
   function removeItem(_item)
   {
      var _loc2_;
      if(typeof _item == "number")
      {
         _loc2_ = _item;
      }
      else
      {
         _loc2_ = this.getIndex(_item);
      }
      if(_loc2_ != undefined)
      {
         this.itemList.splice(_loc2_,1);
      }
   }
   function getIndex(_item)
   {
      for(var _loc2_ in this.itemList)
      {
         if(this.itemList[_loc2_] == _item)
         {
            return _loc2_;
         }
      }
   }
   function getItem(oid)
   {
      var _loc2_;
      for(var _loc4_ in this.itemList)
      {
         if(this.itemList[_loc4_].oID == oid)
         {
            _loc2_ = this.itemList[_loc4_];
            return _loc2_;
         }
      }
   }
   function getItemsCount()
   {
      return this.itemList.length;
   }
   function getItems()
   {
      return this.itemList;
   }
   function getItemsByRoot(rootID)
   {
      var _loc3_ = new Array();
      var _loc2_;
      for(var _loc5_ in this.itemList)
      {
         _loc2_ = this.itemList[_loc5_];
         if(_loc2_.rootID == rootID)
         {
            _loc3_.push(_loc2_);
         }
      }
      return _loc3_;
   }
   function getItemsByType(typeID)
   {
      var _loc3_ = new Array();
      var _loc2_;
      for(var _loc5_ in this.itemList)
      {
         _loc2_ = this.itemList[_loc5_];
         if(_loc2_.typeID == typeID)
         {
            _loc3_.push(_loc2_);
         }
      }
      return _loc3_;
   }
}
