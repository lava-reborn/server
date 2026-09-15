class lol.core.location.LDParser
{
   function LDParser()
   {
   }
   static function parseLD(doc)
   {
      var _loc17_ = doc.firstChild;
      var _loc1_ = _loc17_.childNodes;
      var _loc14_ = new lol.core.location.LocInfo();
      _loc14_.locationName = _loc17_.attributes.title;
      _loc14_.pl_imgID = _loc17_.attributes.preloader;
      _loc14_.bg_soundID = _loc17_.attributes.bgsound;
      if(_loc14_.bg_soundID == "")
      {
         _loc14_.bg_soundID = undefined;
      }
      _loc14_.libraryID = _loc17_.attributes.library;
      _loc14_.width = Number(_loc17_.attributes.width);
      _loc14_.height = Number(_loc17_.attributes.height);
      _loc14_.battle = Boolean(Number(_loc17_.attributes.war));
      _loc14_.sourceName = _loc17_.attributes.fn;
      _loc14_.pvpEnabled = _loc17_.attributes.pvp != "0" ? true : false;
      var _loc16_ = new Array();
      var _loc18_ = new Array();
      var _loc19_;
      var _loc20_;
      var _loc11_ = _loc17_.attributes.bgExt != "ext" ? "lib" : "ext";
      var _loc12_ = {id:_loc17_.attributes.bg,resType:_loc11_};
      var _loc15_;
      var _loc13_;
      var _loc7_;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      var _loc3_;
      var _loc9_;
      var _loc10_;
      var _loc8_;
      var _loc2_;
      for(var _loc21_ in _loc1_)
      {
         if(_loc1_[_loc21_].nodeName == "obstacles")
         {
            _loc15_ = _loc1_[_loc21_].childNodes.join("");
            _loc19_ = lol.core.location.LDParser.getHexCoord(_loc15_,null,null,5);
         }
         else if(_loc1_[_loc21_].nodeName == "zones")
         {
            _loc15_ = _loc1_[_loc21_].childNodes.join("");
            _loc20_ = lol.core.location.LDParser.getHexCoord(_loc15_);
         }
         else if(_loc1_[_loc21_].nodeName == "bgdecoration")
         {
            _loc13_ = _loc1_[_loc21_].attributes.id;
            _loc11_ = _loc1_[_loc21_].attributes.type;
            _loc7_ = Number(_loc1_[_loc21_].attributes.dx);
            _loc6_ = Number(_loc1_[_loc21_].attributes.dy);
            if(isNaN(_loc7_))
            {
               _loc7_ = 0;
            }
            if(isNaN(_loc6_))
            {
               _loc6_ = 0;
            }
            _loc5_ = new Object();
            _loc5_.resID = _loc13_;
            _loc5_.resType = _loc11_;
            _loc5_.dx = _loc7_;
            _loc5_.dy = _loc6_;
            _loc18_.push(_loc5_);
         }
         else if(_loc1_[_loc21_].nodeName == "sprite")
         {
            _loc13_ = _loc1_[_loc21_].attributes.id;
            _loc11_ = !_loc1_[_loc21_].attributes.type ? "lib" : _loc1_[_loc21_].attributes.type;
            _loc7_ = Number(_loc1_[_loc21_].attributes.dx);
            _loc6_ = Number(_loc1_[_loc21_].attributes.dy);
            if(isNaN(_loc7_))
            {
               _loc7_ = 0;
            }
            if(isNaN(_loc6_))
            {
               _loc6_ = 0;
            }
            _loc4_ = lol.core.location.LDParser.getHexCoord(_loc1_[_loc21_].childNodes.join(""));
            _loc3_ = 0;
            while(_loc3_ < _loc4_.length)
            {
               _loc9_ = _loc4_[_loc3_].y - 128;
               _loc10_ = _loc4_[_loc3_].x - 128;
               _loc8_ = lol.core.location.LDParser.getHexCoord(_loc1_[_loc21_].attributes.front,_loc10_,_loc9_);
               _loc2_ = new Object();
               _loc2_.resID = _loc13_;
               _loc2_.resType = _loc11_;
               _loc2_.resDX = _loc7_;
               _loc2_.resDY = _loc6_;
               _loc2_.front_arr = _loc8_;
               _loc2_.point = _loc4_[_loc3_];
               _loc16_.push(_loc2_);
               _loc3_ = _loc3_ + 1;
            }
         }
         else if(_loc1_[_loc21_].nodeName == "background")
         {
            _loc12_ = new Object();
            _loc12_.id = _loc1_[_loc21_].attributes.id;
            _loc12_.resType = _loc1_[_loc21_].attributes.type;
            _loc12_.fx = _loc1_[_loc21_].attributes.fx;
         }
      }
      _loc14_.back = _loc12_;
      _loc14_.obstacles = _loc19_;
      _loc14_.zones = _loc20_;
      _loc14_.sprites = _loc16_;
      _loc14_.bgDecorations = _loc18_;
      return _loc14_;
   }
   static function getHexCoord(str, offX, offY, d)
   {
      var _loc12_ = !d ? 4 : d;
      var _loc13_ = !offX ? 0 : offX;
      var _loc10_ = !offY ? 0 : offY;
      var _loc11_ = new Array();
      var _loc2_ = 0;
      var _loc6_;
      var _loc5_;
      var _loc8_;
      var _loc3_;
      var _loc1_;
      var _loc7_;
      var _loc9_;
      while(_loc2_ < str.length)
      {
         _loc6_ = "0x" + str.substr(_loc2_,2);
         _loc5_ = "0x" + str.substr(_loc2_ + 2,2);
         _loc8_ = Number(_loc6_.toString(10));
         _loc3_ = Number(_loc5_.toString(10));
         _loc1_ = new Object();
         _loc7_ = _loc10_ + 128;
         _loc9_ = !(_loc7_ % 2 > 0 && _loc3_ % 2 > 0) ? 0 : 1;
         _loc1_.x = _loc8_ + _loc13_ + _loc9_;
         _loc1_.y = _loc3_ + _loc10_;
         _loc1_.x16 = _loc1_.x.toString(16);
         _loc1_.y16 = _loc1_.y.toString(16);
         _loc11_.push(_loc1_);
         _loc2_ += _loc12_;
      }
      return _loc11_;
   }
}
