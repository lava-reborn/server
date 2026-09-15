class lol.display.AnimationFactory
{
   var AnimationList;
   var HR;
   var aName;
   var composite;
   var infoLoaded;
   var pType;
   var persName;
   static var persList;
   static var sourceList;
   static var animationEnabled = true;
   function AnimationFactory()
   {
      this.AnimationList = new Array();
      if(!lol.display.AnimationFactory.persList)
      {
         lol.display.AnimationFactory.initialize();
      }
   }
   function init()
   {
      this.killHR();
      this.HR = new lol.server.HTTPRequest();
      this.HR.addEventListener("onXML",this);
      var _loc2_ = lol.display.AnimationFactory.sourceList[this.pType][0](this.persName);
      this.HR.Send("",_loc2_);
   }
   function onXML(obj)
   {
      this.parse(obj.data);
      this.infoLoaded = true;
      this.killHR();
   }
   function killHR()
   {
      this.HR.removeEventListener("onXML",this);
      this.HR.kill();
      this.HR = null;
   }
   function parse(xml_doc)
   {
      var _loc9_ = xml_doc.firstChild;
      var _loc6_ = _loc9_.childNodes;
      var _loc10_ = _loc9_.attributes.composite;
      if(_loc10_ == "true")
      {
         this.composite = true;
      }
      else
      {
         this.composite = false;
      }
      var _loc4_;
      var _loc2_;
      var _loc3_;
      var _loc5_;
      for(var _loc8_ in _loc6_)
      {
         _loc4_ = _loc6_[_loc8_].nodeName;
         this.AnimationList[_loc4_] = [];
         _loc2_ = _loc6_[_loc8_].childNodes;
         for(var _loc7_ in _loc2_)
         {
            _loc3_ = _loc2_[_loc7_].attributes.id;
            this.AnimationList[_loc4_][_loc3_] = {};
            this.AnimationList[_loc4_][_loc3_].action = _loc2_[_loc7_].attributes.action;
            _loc5_ = _loc2_[_loc7_].childNodes.join("").split(",");
            this.AnimationList[_loc4_][_loc3_].sequence = _loc5_;
         }
      }
   }
   function getSource(type_ac_id, ac_id)
   {
      var _loc3_ = this.AnimationList[type_ac_id][ac_id].action;
      var _loc4_ = this.aName + _loc3_;
      var _loc2_ = lol.display.SourceLibrary.getSource(_loc4_);
      var _loc5_;
      if(_loc2_.status != "loaded")
      {
         if(_loc2_.status == "loading")
         {
            _loc2_ = lol.display.SourceLibrary.getSource("default");
         }
         else
         {
            _loc5_ = lol.display.AnimationFactory.sourceList[this.pType][1](this.persName,_loc3_);
            _loc2_.loadSource(_loc5_);
            _loc2_ = lol.display.SourceLibrary.getSource("default");
         }
      }
      return _loc2_;
   }
   function getItemSource(type_ac_id, ac_id, weaponname, primSlotType, primSlotRootType)
   {
      var _loc3_ = this.AnimationList[type_ac_id][ac_id].action;
      weaponname = lol.utils.ParseString.replaceAll(weaponname,"/","");
      var _loc4_ = this.aName + weaponname + _loc3_;
      var _loc2_ = lol.display.SourceLibrary.getSource(_loc4_);
      var _loc6_;
      if(!_loc2_.status)
      {
         if(_loc2_.status != "loading" && _loc3_)
         {
            _loc6_ = lol.services.SSEmulator.getItemAnimURL(this.persName,_loc3_,primSlotType,primSlotRootType);
            _loc2_.loadSource(_loc6_);
         }
      }
      return _loc2_;
   }
   function getFrame(char)
   {
      if(lol.display.AnimationFactory.animationEnabled && this.infoLoaded)
      {
         return this.renderFrame(char);
      }
      char.one_pass_left = false;
      return this.getDefault();
   }
   function renderFrame(char)
   {
      var _loc5_ = char.behaviorType;
      var _loc8_ = char.behavior;
      var _loc21_ = char.currentFrameNumber;
      var _loc14_ = char.direction;
      var _loc9_ = this.AnimationList[_loc5_][_loc8_].sequence;
      var _loc24_ = _loc9_.length;
      var _loc6_ = this.getSource(_loc5_,_loc8_);
      var _loc15_ = (_loc6_._length - 2) / 8;
      var _loc19_ = Number(_loc9_[_loc21_]);
      var _loc4_ = 2 + _loc15_ * (_loc14_ - 1) + _loc19_;
      var _loc20_ = _loc6_.getBitmap(_loc4_);
      var _loc26_ = _loc20_.clone();
      var _loc2_ = _loc6_.getOffset(_loc4_);
      if(!_loc26_)
      {
         _loc26_ = lol.display.SourceLibrary.getSource("default").getBitmap(1).clone();
         _loc2_ = lol.display.SourceLibrary.getSource("default").getOffset(1);
      }
      var _loc7_;
      var _loc22_;
      var _loc23_;
      var _loc17_;
      var _loc11_;
      var _loc13_;
      var _loc10_;
      var _loc18_;
      var _loc16_;
      if(_loc5_ != "fist" && this.composite)
      {
         _loc7_ = lol.core.Master.getInstance().getPlayer(char.id);
         _loc22_ = _loc7_.primaryItem.itemName;
         _loc23_ = _loc7_.primaryItem.typeID;
         _loc17_ = _loc7_.primaryItem.rootID;
         _loc11_ = this.getItemSource(_loc5_,_loc8_,_loc22_,_loc23_,_loc17_);
         _loc13_ = _loc11_.getBitmap(_loc4_);
         _loc10_ = _loc11_.getOffset(_loc4_);
         _loc18_ = _loc10_.dx - _loc2_.dx;
         _loc16_ = _loc10_.dy - _loc2_.dy;
         _loc26_.copyPixels(_loc13_,new flash.geom.Rectangle(0,0,_loc26_.width,_loc26_.height),new flash.geom.Point(_loc18_,_loc16_),null,null,true);
      }
      var _loc12_ = {bitmap:_loc26_,offset:_loc2_,length:_loc24_};
      char.is_default = false;
      return _loc12_;
   }
   function getDefault()
   {
      var _loc1_ = lol.display.SourceLibrary.getSource("default");
      if(!_loc1_.status)
      {
         lol.services.SSEmulator.loadDefault();
      }
      var _loc3_ = _loc1_.getBitmap(1);
      var _loc6_ = _loc3_.clone();
      var _loc4_ = 1;
      var _loc5_ = _loc1_.getOffset(1);
      var _loc2_ = {bitmap:_loc6_,offset:_loc5_,length:_loc4_};
      return _loc2_;
   }
   static function initialize()
   {
      lol.display.AnimationFactory.persList = new Array();
      lol.display.AnimationFactory.sourceList = new Array();
      lol.display.AnimationFactory.sourceList.mob = [lol.services.SSEmulator.getMobInfoURL,lol.services.SSEmulator.getMobAnimURL];
      lol.display.AnimationFactory.sourceList.player = [lol.services.SSEmulator.getPersInfoURL,lol.services.SSEmulator.getPersAnimURL];
   }
   static function getAF(pType, persName)
   {
      var _loc2_ = pType + persName;
      var _loc1_;
      if(!lol.display.AnimationFactory.persList[_loc2_])
      {
         _loc1_ = new lol.display.AnimationFactory();
         _loc1_.pType = pType;
         _loc1_.persName = persName;
         _loc1_.aName = _loc2_;
         _loc1_.init();
         lol.display.AnimationFactory.persList[_loc2_] = _loc1_;
      }
      return lol.display.AnimationFactory.persList[_loc2_];
   }
}
