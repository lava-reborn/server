class lol.data.BigUINTCluster
{
   var size;
   var value;
   function BigUINTCluster(val, s)
   {
      this.value = val;
      this.size = s;
   }
   function toString()
   {
      var _loc3_ = "";
      var _loc5_ = this.value.toString(16);
      var _loc4_;
      var _loc2_;
      if(this.size)
      {
         _loc4_ = _loc5_.length;
         _loc2_ = 0;
         while(_loc2_ < this.size - _loc4_)
         {
            _loc3_ += "0";
            _loc2_ = _loc2_ + 1;
         }
      }
      _loc3_ += _loc5_;
      return _loc3_;
   }
}
