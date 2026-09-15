class lol.gpui.DDOperation
{
   var fromItem;
   var fromItemMc;
   var fromItemMc_arr;
   var fromSlot;
   var toItem;
   var toItemMc;
   var toSlot;
   function DDOperation()
   {
   }
   function successOperation()
   {
      this.toItemMc.unblockItem();
      this.fromItemMc.unblockItem();
      for(var _loc2_ in this.fromItemMc_arr)
      {
         this.fromItemMc_arr[_loc2_].unblockItem();
      }
   }
   function failedOperation()
   {
      this.toItemMc.unblockItem();
      this.fromItemMc.unblockItem();
      for(var _loc2_ in this.fromItemMc_arr)
      {
         this.fromItemMc_arr[_loc2_].unblockItem();
      }
   }
   function setFrom(dragItem, _fromSlot, _fromItemMc, _fromItemArr)
   {
      if(dragItem)
      {
         this.fromItem = dragItem;
      }
      if(_fromSlot)
      {
         this.fromSlot = _fromSlot;
      }
      if(_fromItemMc)
      {
         this.fromItemMc = _fromItemMc;
      }
      if(_fromItemArr)
      {
         this.fromItemMc_arr = _fromItemArr;
      }
      this.fromItemMc.blockItem();
   }
   function setTo(hittedItem, _toSlot, _toItemMc)
   {
      if(hittedItem)
      {
         this.toItem = hittedItem;
      }
      if(_toSlot)
      {
         this.toSlot = _toSlot;
      }
      if(_toItemMc)
      {
         this.toItemMc = _toItemMc;
      }
   }
   function get firstItem()
   {
      return this.fromItemMc_arr[0].item;
   }
   function get group()
   {
      if(this.fromItemMc_arr.length > 1)
      {
         return true;
      }
      return false;
   }
}
