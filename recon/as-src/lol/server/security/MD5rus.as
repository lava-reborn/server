class lol.server.security.MD5rus
{
   var hex_chr = "0123456789abcdef";
   function MD5rus()
   {
   }
   function bitOR(a, b)
   {
      var _loc1_ = a & 1 | b & 1;
      var _loc2_ = a >>> 1 | b >>> 1;
      return _loc2_ << 1 | _loc1_;
   }
   function bitXOR(a, b)
   {
      var _loc1_ = a & 1 ^ b & 1;
      var _loc2_ = a >>> 1 ^ b >>> 1;
      return _loc2_ << 1 | _loc1_;
   }
   function bitAND(a, b)
   {
      var _loc1_ = a & 1 & (b & 1);
      var _loc2_ = a >>> 1 & b >>> 1;
      return _loc2_ << 1 | _loc1_;
   }
   function addme(x, y)
   {
      var _loc1_ = (x & 0xFFFF) + (y & 0xFFFF);
      var _loc2_ = (x >> 16) + (y >> 16) + (_loc1_ >> 16);
      return _loc2_ << 16 | _loc1_ & 0xFFFF;
   }
   function rhex(num)
   {
      var _loc4_ = "";
      var _loc2_ = 0;
      while(_loc2_ <= 3)
      {
         _loc4_ += this.hex_chr.charAt(num >> _loc2_ * 8 + 4 & 0x0F) + this.hex_chr.charAt(num >> _loc2_ * 8 & 0x0F);
         _loc2_ = _loc2_ + 1;
      }
      return _loc4_;
   }
   function str2blks_MD5(str)
   {
      var _loc1_;
      var _loc4_ = (str.length + 8 >> 6) + 1;
      var _loc3_ = new Array(_loc4_ * 16);
      _loc1_ = 0;
      while(_loc1_ < _loc4_ * 16)
      {
         _loc3_[_loc1_] = 0;
         _loc1_ = _loc1_ + 1;
      }
      _loc1_ = 0;
      while(_loc1_ < str.length)
      {
         _loc3_[_loc1_ >> 2] |= str[_loc1_] << (str.length * 8 + _loc1_) % 4 * 8;
         _loc1_ = _loc1_ + 1;
      }
      _loc3_[_loc1_ >> 2] |= 128 << (str.length * 8 + _loc1_) % 4 * 8;
      var _loc5_ = str.length * 8;
      _loc3_[_loc4_ * 16 - 2] = _loc5_ & 0xFF;
      _loc3_[_loc4_ * 16 - 2] |= (_loc5_ >>> 8 & 0xFF) << 8;
      _loc3_[_loc4_ * 16 - 2] |= (_loc5_ >>> 16 & 0xFF) << 16;
      _loc3_[_loc4_ * 16 - 2] |= (_loc5_ >>> 24 & 0xFF) << 24;
      return _loc3_;
   }
   function rol(num, cnt)
   {
      return num << cnt | num >>> 32 - cnt;
   }
   function cmn(q, a, b, x, s, t)
   {
      return this.addme(this.rol(this.addme(this.addme(a,q),this.addme(x,t)),s),b);
   }
   function ff(a, b, c, d, x, s, t)
   {
      return this.cmn(this.bitOR(this.bitAND(b,c),this.bitAND(~b,d)),a,b,x,s,t);
   }
   function gg(a, b, c, d, x, s, t)
   {
      return this.cmn(this.bitOR(this.bitAND(b,d),this.bitAND(c,~d)),a,b,x,s,t);
   }
   function hh(a, b, c, d, x, s, t)
   {
      return this.cmn(this.bitXOR(this.bitXOR(b,c),d),a,b,x,s,t);
   }
   function ii(a, b, c, d, x, s, t)
   {
      return this.cmn(this.bitXOR(c,this.bitOR(b,~d)),a,b,x,s,t);
   }
   function calcMD5(str)
   {
      var _loc7_ = this.str2blks_MD5(str);
      var _loc5_ = 1732584193;
      var _loc4_ = -271733879;
      var _loc3_ = -1732584194;
      var _loc2_ = 271733878;
      var _loc12_;
      var _loc6_ = 0;
      var _loc11_;
      var _loc10_;
      var _loc9_;
      var _loc8_;
      while(_loc6_ < _loc7_.length)
      {
         _loc11_ = _loc5_;
         _loc10_ = _loc4_;
         _loc9_ = _loc3_;
         _loc8_ = _loc2_;
         _loc12_ = 0;
         _loc5_ = this.ff(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 0],7,-680876936);
         _loc2_ = this.ff(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 1],12,-389564586);
         _loc3_ = this.ff(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 2],17,606105819);
         _loc4_ = this.ff(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 3],22,-1044525330);
         _loc5_ = this.ff(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 4],7,-176418897);
         _loc2_ = this.ff(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 5],12,1200080426);
         _loc3_ = this.ff(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 6],17,-1473231341);
         _loc4_ = this.ff(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 7],22,-45705983);
         _loc5_ = this.ff(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 8],7,1770035416);
         _loc2_ = this.ff(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 9],12,-1958414417);
         _loc3_ = this.ff(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 10],17,-42063);
         _loc4_ = this.ff(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 11],22,-1990404162);
         _loc5_ = this.ff(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 12],7,1804603682);
         _loc2_ = this.ff(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 13],12,-40341101);
         _loc3_ = this.ff(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 14],17,-1502002290);
         _loc4_ = this.ff(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 15],22,1236535329);
         _loc5_ = this.gg(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 1],5,-165796510);
         _loc2_ = this.gg(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 6],9,-1069501632);
         _loc3_ = this.gg(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 11],14,643717713);
         _loc4_ = this.gg(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 0],20,-373897302);
         _loc5_ = this.gg(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 5],5,-701558691);
         _loc2_ = this.gg(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 10],9,38016083);
         _loc3_ = this.gg(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 15],14,-660478335);
         _loc4_ = this.gg(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 4],20,-405537848);
         _loc5_ = this.gg(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 9],5,568446438);
         _loc2_ = this.gg(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 14],9,-1019803690);
         _loc3_ = this.gg(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 3],14,-187363961);
         _loc4_ = this.gg(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 8],20,1163531501);
         _loc5_ = this.gg(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 13],5,-1444681467);
         _loc2_ = this.gg(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 2],9,-51403784);
         _loc3_ = this.gg(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 7],14,1735328473);
         _loc4_ = this.gg(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 12],20,-1926607734);
         _loc5_ = this.hh(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 5],4,-378558);
         _loc2_ = this.hh(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 8],11,-2022574463);
         _loc3_ = this.hh(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 11],16,1839030562);
         _loc4_ = this.hh(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 14],23,-35309556);
         _loc5_ = this.hh(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 1],4,-1530992060);
         _loc2_ = this.hh(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 4],11,1272893353);
         _loc3_ = this.hh(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 7],16,-155497632);
         _loc4_ = this.hh(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 10],23,-1094730640);
         _loc5_ = this.hh(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 13],4,681279174);
         _loc2_ = this.hh(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 0],11,-358537222);
         _loc3_ = this.hh(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 3],16,-722521979);
         _loc4_ = this.hh(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 6],23,76029189);
         _loc5_ = this.hh(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 9],4,-640364487);
         _loc2_ = this.hh(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 12],11,-421815835);
         _loc3_ = this.hh(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 15],16,530742520);
         _loc4_ = this.hh(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 2],23,-995338651);
         _loc5_ = this.ii(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 0],6,-198630844);
         _loc2_ = this.ii(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 7],10,1126891415);
         _loc3_ = this.ii(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 14],15,-1416354905);
         _loc4_ = this.ii(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 5],21,-57434055);
         _loc5_ = this.ii(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 12],6,1700485571);
         _loc2_ = this.ii(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 3],10,-1894986606);
         _loc3_ = this.ii(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 10],15,-1051523);
         _loc4_ = this.ii(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 1],21,-2054922799);
         _loc5_ = this.ii(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 8],6,1873313359);
         _loc2_ = this.ii(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 15],10,-30611744);
         _loc3_ = this.ii(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 6],15,-1560198380);
         _loc4_ = this.ii(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 13],21,1309151649);
         _loc5_ = this.ii(_loc5_,_loc4_,_loc3_,_loc2_,_loc7_[_loc6_ + 4],6,-145523070);
         _loc2_ = this.ii(_loc2_,_loc5_,_loc4_,_loc3_,_loc7_[_loc6_ + 11],10,-1120210379);
         _loc3_ = this.ii(_loc3_,_loc2_,_loc5_,_loc4_,_loc7_[_loc6_ + 2],15,718787259);
         _loc4_ = this.ii(_loc4_,_loc3_,_loc2_,_loc5_,_loc7_[_loc6_ + 9],21,-343485551);
         _loc5_ = this.addme(_loc5_,_loc11_);
         _loc4_ = this.addme(_loc4_,_loc10_);
         _loc3_ = this.addme(_loc3_,_loc9_);
         _loc2_ = this.addme(_loc2_,_loc8_);
         _loc6_ += 16;
      }
      return this.rhex(_loc5_) + this.rhex(_loc4_) + this.rhex(_loc3_) + this.rhex(_loc2_);
   }
   function hashMD5(str)
   {
      var _loc4_ = str.split("").reverse();
      var _loc5_ = new Array();
      var _loc3_;
      var _loc2_;
      while(_loc4_.length > 0)
      {
         _loc3_ = _loc4_.pop();
         _loc2_ = _loc3_.charCodeAt(0);
         if(_loc2_ >= 1040 && _loc2_ <= 1103)
         {
            _loc2_ -= 848;
         }
         if(_loc2_ == 1105)
         {
            _loc2_ = 184;
         }
         if(_loc2_ == 1025)
         {
            _loc2_ = 168;
         }
         _loc5_.push(_loc2_);
      }
      return this.calcMD5(_loc5_);
   }
   static function convertToCP1251(str)
   {
      var _loc3_ = str.split("").reverse();
      var _loc5_ = new Array();
      var _loc4_;
      var _loc2_;
      var _loc1_;
      while(_loc3_.length > 0)
      {
         _loc2_ = _loc3_.pop();
         _loc1_ = _loc2_.charCodeAt(0);
         if(_loc1_ >= 1040 && _loc1_ <= 1103)
         {
            _loc1_ -= 848;
         }
         if(_loc1_ == 1105)
         {
            _loc1_ = 184;
         }
         if(_loc1_ == 1025)
         {
            _loc1_ = 168;
         }
         _loc4_ = _loc1_.toString(16);
         _loc5_.push("%" + _loc4_);
      }
      return _loc5_.join("");
   }
}
