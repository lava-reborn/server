class lol.utils.MDString
{
   function MDString()
   {
   }
   static function arrayToString(arr)
   {
      var _loc1_ = "|" + arr.join("|") + "|";
      return _loc1_;
   }
   static function stringToArray(str)
   {
      var _loc1_ = str.split("|");
      _loc1_.shift();
      _loc1_.pop();
      return _loc1_;
   }
   static function createBigUINT()
   {
      var _loc6_ = arguments;
      var _loc7_ = "";
      var _loc10_ = _loc6_.length;
      var _loc8_ = _loc6_[0][0].toString(16);
      _loc7_ += _loc8_;
      var _loc3_ = 1;
      var _loc9_;
      var _loc5_;
      var _loc4_;
      var _loc2_;
      while(_loc3_ < _loc10_)
      {
         _loc9_ = _loc6_[_loc3_];
         _loc8_ = _loc6_[_loc3_][0].toString(16);
         _loc5_ = _loc6_[_loc3_][1];
         _loc4_ = _loc8_.length;
         if(_loc4_)
         {
            _loc2_ = 0;
            while(_loc2_ < _loc5_ - _loc4_)
            {
               _loc7_ += "0";
               _loc2_ = _loc2_ + 1;
            }
         }
         _loc7_ += _loc8_;
         _loc3_ = _loc3_ + 1;
      }
      return _loc7_;
   }
   static function parseBigUINT(buint)
   {
      var _loc5_ = new Array();
      var _loc2_;
      var _loc7_ = arguments.length;
      var _loc4_;
      var _loc3_ = buint.length;
      _loc2_ = _loc7_ - 1;
      while(_loc2_ >= 1)
      {
         _loc4_ = Number("0x" + buint.slice(_loc3_ - arguments[_loc2_],_loc3_));
         _loc5_.push(_loc4_);
         _loc3_ -= arguments[_loc2_];
         _loc2_ = _loc2_ - 1;
      }
      _loc4_ = Number("0x" + buint.slice(0,_loc3_));
      _loc5_.push(_loc4_);
      return _loc5_;
   }
}
