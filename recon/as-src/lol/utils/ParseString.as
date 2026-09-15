class lol.utils.ParseString
{
   static var SEX = "sex";
   static var STR_PAD_LEFT = 0;
   static var STR_PAD_RIGHT = 1;
   function ParseString()
   {
   }
   static function parse(temp_str)
   {
      var _loc3_;
      var _loc2_;
      if(temp_str)
      {
         _loc3_ = true;
         while(_loc3_)
         {
            _loc2_ = temp_str.indexOf("\\",0);
            if(_loc2_ != -1)
            {
               temp_str = temp_str.substring(0,_loc2_) + temp_str.substring(_loc2_ + 2,temp_str.length);
            }
            else
            {
               _loc3_ = false;
            }
         }
         _loc3_ = true;
         while(_loc3_)
         {
            _loc2_ = temp_str.indexOf("quot;",0);
            if(_loc2_ != -1)
            {
               temp_str = temp_str.substring(0,_loc2_) + "\"" + temp_str.substring(_loc2_ + 5,temp_str.length);
            }
            else
            {
               _loc3_ = false;
            }
         }
      }
      return temp_str;
   }
   static function replace(sourceString, strA, strB, count)
   {
      if(count == undefined)
      {
         count = 0;
      }
      var _loc2_ = sourceString.indexOf(strA,count);
      var _loc3_ = strA.length;
      if(_loc2_ != -1)
      {
         sourceString = sourceString.substring(0,_loc2_) + strB + sourceString.substring(_loc2_ + _loc3_,sourceString.length);
      }
      return sourceString;
   }
   static function replaceAll(sourceString, strA, strB)
   {
      return lol.utils.ParseString.__replaceAll(sourceString,strA,strB,0);
   }
   static function __replaceAll(sourceString, strA, strB, count)
   {
      var _loc2_ = sourceString.indexOf(strA,count);
      var _loc3_ = strA.length;
      if(_loc2_ != -1)
      {
         sourceString = sourceString.substring(0,_loc2_) + strB + sourceString.substring(_loc2_ + _loc3_,sourceString.length);
         sourceString = lol.utils.ParseString.__replaceAll(sourceString,strA,strB,_loc2_ + strB.length);
      }
      return sourceString;
   }
   static function replaceParametrically(str, paramName, paramValue)
   {
      var _loc3_ = str.indexOf("%" + paramName,0);
      var _loc7_;
      var _loc2_;
      var _loc5_;
      var _loc6_;
      var _loc4_;
      var _loc8_;
      if(_loc3_ != -1)
      {
         _loc7_ = str.indexOf("%",_loc3_ + 1);
         _loc2_ = str.substring(_loc3_,_loc7_ + 1);
         _loc5_ = _loc2_.indexOf("?",0);
         _loc6_ = _loc2_.substring(_loc5_ + 1,_loc2_.length - 1);
         _loc4_ = _loc6_.split(":");
         _loc8_ = _loc4_[paramValue];
         str = lol.utils.ParseString.replaceAll(str,_loc2_,_loc8_);
         return lol.utils.ParseString.replaceParametrically(str,paramName,paramValue);
      }
      return str;
   }
   static function strPad(str, char, num, from)
   {
      str = String(str);
      var _loc6_ = str.length;
      var _loc2_;
      var _loc1_;
      if(_loc6_ < num)
      {
         _loc2_ = "";
         num -= _loc6_;
         _loc1_ = 0;
         while(_loc1_ < num)
         {
            _loc2_ += char;
            _loc1_ = _loc1_ + 1;
         }
         if(from == lol.utils.ParseString.STR_PAD_LEFT)
         {
            str = _loc2_ + str;
         }
         else if(from == lol.utils.ParseString.STR_PAD_RIGHT)
         {
            str += _loc2_;
         }
      }
      return str;
   }
}
