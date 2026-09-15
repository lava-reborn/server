class lol.core.objects.TransferObject
{
   var __from;
   var __heapNum;
   var __hitted;
   var __item;
   var __newItem;
   var __to;
   function TransferObject()
   {
   }
   function get from()
   {
      return this.__from;
   }
   function set from(f)
   {
      this.__from = f;
   }
   function get to()
   {
      return this.__to;
   }
   function set to(t)
   {
      this.__to = t;
   }
   function get item()
   {
      return this.__item;
   }
   function set item(i)
   {
      this.__item = i;
   }
   function get newItem()
   {
      return this.__newItem;
   }
   function set newItem(ni)
   {
      this.__newItem = ni;
   }
   function get hitted()
   {
      return this.__hitted;
   }
   function set hitted(h)
   {
      this.__hitted = h;
   }
   function get heapNum()
   {
      return this.__heapNum;
   }
   function set heapNum(h)
   {
      this.__heapNum = h;
   }
}
