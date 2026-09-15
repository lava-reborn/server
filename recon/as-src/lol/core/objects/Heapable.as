class lol.core.objects.Heapable extends lol.core.objects.Item
{
   var __quantity;
   var _weight;
   var getProp;
   var max_count;
   var setProp;
   var size;
   var stored_type;
   static var className = "Heapable";
   var __className = "Heapable";
   function Heapable(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
   }
   function initialize(obj)
   {
      this.max_count = obj.max_count;
      super.initialize(obj);
   }
   function get weight()
   {
      var _loc2_ = this.getProp("size");
      var _loc3_ = this.getProp("_weight");
      var _loc4_ = !_loc2_ ? _loc3_ : _loc2_ * _loc3_;
      return _loc4_;
   }
   function get maxCount()
   {
      return this.getProp("max_count");
   }
   function set maxCount(tMaxCount)
   {
      this.setProp("max_count",tMaxCount);
   }
   function set weight(w)
   {
      this._weight = w;
   }
   function get _quantity()
   {
      return this.__quantity;
   }
   function set bonusActiveTime(tQuantity)
   {
      this.__quantity = tQuantity;
   }
   function get storedType()
   {
      return this.stored_type;
   }
   function set storedType(tStoredType)
   {
      this.stored_type = tStoredType;
   }
   function get heapSize()
   {
      return this.size;
   }
   function set heapSize(tHeapSize)
   {
      this.size = tHeapSize;
   }
}
