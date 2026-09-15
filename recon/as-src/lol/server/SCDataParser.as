class lol.server.SCDataParser
{
   function SCDataParser()
   {
   }
   function getCmdName(source)
   {
      var _loc2_ = source.indexOf(";");
      var _loc1_ = source.substring(0,_loc2_);
      return _loc1_;
   }
   function getData(source, paramName)
   {
      var _loc3_ = this.getValueIndex(source,paramName);
      if(_loc3_ == -1)
      {
         return null;
      }
      var _loc2_ = source.charAt(_loc3_);
      if(!isNaN(_loc2_) || _loc2_ == "+" || _loc2_ == "-")
      {
         return this.getDigitData(source,_loc3_);
      }
      if(_loc2_ == "@")
      {
         return this.getStringData(source,_loc3_);
      }
      if(_loc2_ == "H" || _loc2_ == "h")
      {
         return this.getHexData(source,_loc3_);
      }
      if(_loc2_ == "|")
      {
         return this.getListData(source,_loc3_);
      }
      if(_loc2_ == "x")
      {
         return this.getBigUINTData(source,_loc3_);
      }
      return undefined;
   }
   function getPNames(source)
   {
      var _loc5_ = new Array();
      var _loc1_ = 0;
      var _loc6_;
      var _loc2_ = 0;
      var _loc4_;
      while(_loc1_ >= 0)
      {
         _loc1_ = source.indexOf("=",_loc1_ + 1);
         if(_loc1_ == -1)
         {
            break;
         }
         _loc2_ = source.indexOf(";",_loc2_ + 1);
         _loc4_ = source.substring(_loc2_ + 1,_loc1_);
         _loc5_.push(_loc4_);
      }
      return _loc5_;
   }
   function getValueIndex(source, paramName)
   {
      var _loc1_ = source.indexOf(paramName + "=");
      if(_loc1_ == -1)
      {
         return -1;
      }
      return _loc1_ + paramName.length + 1;
   }
   function parse(source)
   {
      var _loc5_ = {};
      var _loc7_ = 0;
      var _loc3_;
      var _loc8_ = 0;
      var _loc2_;
      var _loc11_;
      var _loc6_;
      var _loc9_;
      var _loc10_;
      while(_loc7_ >= 0)
      {
         _loc7_ = source.indexOf("=",_loc7_ + 1);
         if(_loc7_ == -1)
         {
            break;
         }
         _loc8_ = source.indexOf(";",_loc8_ + 1);
         _loc2_ = source.substring(_loc8_ + 1,_loc7_);
         _loc6_ = _loc7_ + 1;
         _loc3_ = source.charAt(_loc6_);
         if(!isNaN(_loc3_) || _loc3_ == "+" || _loc3_ == "-")
         {
            _loc5_[_loc2_] = this.getDigitData(source,_loc6_);
         }
         else if(_loc3_ == "@")
         {
            _loc5_[_loc2_] = this.getStringData(source,_loc6_);
            if(_loc5_[_loc2_].length > 0)
            {
               _loc9_ = _loc2_.length + 2 + _loc5_[_loc2_].length;
               _loc10_ = 2 + _loc5_[_loc2_].length;
               _loc8_ += _loc9_;
               _loc7_ += _loc10_;
            }
         }
         else if(_loc3_ == "H" || _loc3_ == "h")
         {
            _loc5_[_loc2_] = this.getHexData(source,_loc6_);
         }
         else if(_loc3_ == "|")
         {
            _loc5_[_loc2_] = this.getListData(source,_loc6_);
         }
         else if(_loc3_ == "x")
         {
            _loc5_[_loc2_] = this.getBigUINTData(source,_loc6_);
         }
      }
      return _loc5_;
   }
   function getStringData(str, i)
   {
      var _loc2_ = str.indexOf("@;",i + 1);
      str = str.slice(i + 1,_loc2_);
      str = lol.server.XMLString.unescape(str);
      return str;
   }
   function getDigitData(str, i)
   {
      var _loc1_ = str.indexOf(";",i);
      return Number(str.slice(i,_loc1_));
   }
   function getHexData(str, i)
   {
      var _loc1_ = str.indexOf(";",i);
      return Number(str.slice(i + 1,_loc1_));
   }
   function getBigUINTData(str, i)
   {
      var _loc1_ = str.indexOf(";",i);
      return str.slice(i + 1,_loc1_);
   }
   function getListData(str, i)
   {
      var _loc3_ = str.charAt(i + 1);
      var _loc2_;
      if(_loc3_ == ";")
      {
         _loc2_ = [];
      }
      else if(_loc3_ == "@")
      {
         _loc2_ = this.getStringListData(str,i);
      }
      else if(_loc3_ == "x")
      {
         _loc2_ = this.getBigUINListData(str,i);
      }
      else
      {
         _loc2_ = this.getDigitListData(str,i);
      }
      return _loc2_;
   }
   function getDigitListData(str, i)
   {
      var _loc5_ = str.indexOf("|;",i);
      str = str.slice(i + 1,_loc5_);
      var _loc2_ = str.split("|");
      var _loc3_ = _loc2_.length;
      var _loc1_ = 0;
      while(_loc1_ < _loc3_)
      {
         _loc2_[_loc1_] = Number(_loc2_[_loc1_]);
         _loc1_ = _loc1_ + 1;
      }
      return _loc2_;
   }
   function getStringListData(str, i)
   {
      var _loc3_ = str.indexOf("@|;",i);
      str = str.slice(i + 2,_loc3_);
      var _loc2_ = str.split("@|@");
      return _loc2_;
   }
   function getBigUINListData(str, i)
   {
      var _loc5_ = str.indexOf("|;",i);
      str = str.slice(i + 1,_loc5_);
      var _loc2_ = str.split("|");
      var _loc3_ = _loc2_.length;
      var _loc1_ = 0;
      while(_loc1_ < _loc3_)
      {
         _loc2_[_loc1_] = _loc2_[_loc1_].slice(1);
         _loc1_ = _loc1_ + 1;
      }
      return _loc2_;
   }
}
