class mx.utils.XMLString
{
   static var escChars;
   static var unescChars;
   static var _ref = new mx.utils.XMLString();
   function XMLString()
   {
      mx.utils.XMLString.escChars = {};
      mx.utils.XMLString.escChars["<"] = "&lt;";
      mx.utils.XMLString.escChars[">"] = "&gt;";
      mx.utils.XMLString.escChars["\'"] = "&apos;";
      mx.utils.XMLString.escChars["\""] = "&quot;";
      mx.utils.XMLString.escChars["&"] = "&amp;";
      mx.utils.XMLString.unescChars = {};
      mx.utils.XMLString.unescChars["&amp;"] = "&";
      mx.utils.XMLString.unescChars["&apos;"] = "\'";
      mx.utils.XMLString.unescChars["&quot;"] = "\"";
      mx.utils.XMLString.unescChars["&lt;"] = "<";
      mx.utils.XMLString.unescChars["&gt;"] = ">";
   }
   static function escape(val)
   {
      var _loc3_ = "";
      var _loc2_;
      var _loc1_ = 0;
      while(_loc1_ < val.length)
      {
         _loc2_ = val.charAt(_loc1_);
         if(mx.utils.XMLString.escChars[_loc2_] != undefined)
         {
            _loc3_ += mx.utils.XMLString.escChars[_loc2_];
         }
         else
         {
            _loc3_ += _loc2_;
         }
         _loc1_ = _loc1_ + 1;
      }
      return _loc3_;
   }
   static function unescape(val)
   {
      var _loc1_ = 0;
      var _loc4_ = 0;
      var _loc3_ = 0;
      if(val != null)
      {
         for(var _loc5_ in mx.utils.XMLString.unescChars)
         {
            _loc4_ = String(_loc5_).length;
            _loc1_ = val.indexOf(_loc5_,0);
            _loc3_ = _loc1_;
            while(_loc1_ != -1)
            {
               val = val.substring(0,_loc1_) + mx.utils.XMLString.unescChars[_loc5_] + val.substring(_loc1_ + _loc4_);
               _loc1_ = val.indexOf(_loc5_,0);
               if(_loc3_ == _loc1_)
               {
                  _loc1_ = -1;
               }
               _loc3_ = _loc1_;
            }
         }
      }
      return val;
   }
}
