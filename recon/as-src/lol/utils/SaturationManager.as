class lol.utils.SaturationManager
{
   function SaturationManager()
   {
   }
   static function setSaturation(object, amount)
   {
      amount /= 100;
      var _loc4_ = new flash.filters.ColorMatrixFilter();
      var _loc7_ = [1,0,0,0,0];
      var _loc8_ = [0,1,0,0,0];
      var _loc6_ = [0,0,1,0,0];
      var _loc5_ = [0,0,0,1,0];
      var _loc2_ = [0.3,0.59,0.11,0,0];
      var _loc1_ = new Array();
      _loc1_ = _loc1_.concat(lol.utils.SaturationManager.interpolateArrays(_loc2_,_loc7_,amount));
      _loc1_ = _loc1_.concat(lol.utils.SaturationManager.interpolateArrays(_loc2_,_loc8_,amount));
      _loc1_ = _loc1_.concat(lol.utils.SaturationManager.interpolateArrays(_loc2_,_loc6_,amount));
      _loc1_ = _loc1_.concat(_loc5_);
      _loc4_.matrix = _loc1_;
      object.filters = [_loc4_];
   }
   static function interpolateArrays(ary1, ary2, t)
   {
      var _loc3_ = ary1.length < ary2.length ? ary2.slice() : ary1.slice();
      var _loc1_ = _loc3_.length;
      while(_loc1_--)
      {
         _loc3_[_loc1_] = ary1[_loc1_] + (ary2[_loc1_] - ary1[_loc1_]) * t;
      }
      return _loc3_;
   }
}
