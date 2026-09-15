class lol.server.XMLString
{
   static var escChars;
   static var unescChars;
   static var _ref = new lol.server.XMLString();
   function XMLString()
   {
      lol.server.XMLString.escChars = {};
      lol.server.XMLString.escChars["<"] = "%3C";
      lol.server.XMLString.escChars[">"] = "%3E";
      lol.server.XMLString.escChars["\'"] = "%27";
      lol.server.XMLString.escChars["\""] = "%5C";
      lol.server.XMLString.escChars["&"] = "%26";
      lol.server.XMLString.escChars["@"] = "%40";
      lol.server.XMLString.escChars["%"] = "%25";
      lol.server.XMLString.unescChars = {};
      lol.server.XMLString.unescChars["%3C"] = "<";
      lol.server.XMLString.unescChars["%3E"] = ">";
      lol.server.XMLString.unescChars["%27"] = "\'";
      lol.server.XMLString.unescChars["%5C"] = "\"";
      lol.server.XMLString.unescChars["%26"] = "&";
      lol.server.XMLString.unescChars["%40"] = "@";
      lol.server.XMLString.unescChars["%25"] = "%";
   }
   static function escape(val)
   {
      var _loc3_ = "";
      var _loc2_;
      var _loc1_ = 0;
      while(_loc1_ < val.length)
      {
         _loc2_ = val.charAt(_loc1_);
         if(lol.server.XMLString.escChars[_loc2_] != undefined)
         {
            _loc3_ += lol.server.XMLString.escChars[_loc2_];
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
         for(var _loc5_ in lol.server.XMLString.unescChars)
         {
            _loc4_ = String(_loc5_).length;
            _loc1_ = val.indexOf(_loc5_,0);
            _loc3_ = _loc1_;
            while(_loc1_ != -1)
            {
               val = val.substring(0,_loc1_) + lol.server.XMLString.unescChars[_loc5_] + val.substring(_loc1_ + _loc4_);
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
