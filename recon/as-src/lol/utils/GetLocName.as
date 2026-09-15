class lol.utils.GetLocName
{
   var HTTP;
   var dispatchEvent;
   var locations;
   static var instance = new lol.utils.GetLocName();
   function GetLocName()
   {
      lol.events.LEventDispatcher.initialize(this);
   }
   function loadXML()
   {
      this.HTTP = new lol.server.HTTPRequest();
      this.HTTP.addEventListener("onXML",this);
      this.HTTP.addEventListener("failed",this);
      var _loc2_ = lol.services.SSEmulator.getLoacNameXmlURL();
      this.HTTP.Send("",_loc2_);
   }
   function onXML(obj)
   {
      var _loc7_ = obj.data;
      this.HTTP.removeEventListener("onXML",this);
      this.HTTP.kill();
      this.HTTP = null;
      this.locations = new Array();
      var _loc6_ = _loc7_.firstChild.childNodes;
      var _loc3_ = 0;
      var _loc2_;
      var _loc5_;
      var _loc4_;
      while(_loc3_ < _loc6_.length)
      {
         _loc2_ = _loc6_[_loc3_];
         _loc5_ = _loc2_.attributes.x + "_" + _loc2_.attributes.y;
         _loc4_ = _loc2_.attributes.text;
         this.locations[_loc5_] = _loc4_;
         _loc3_ = _loc3_ + 1;
      }
      this.dispatchEvent({type:"onLoad"});
      lol.core.SceneShifter.main.dPan.loadingReport("ok. " + lol.services.SSEmulator.getLoacNameXmlURL());
   }
   function failed()
   {
      this.dispatchEvent({type:"failed"});
      lol.core.SceneShifter.main.dPan.loadingReport("error. " + lol.services.SSEmulator.getLoacNameXmlURL());
   }
   function getName(x, y)
   {
      var _loc2_ = this.locations[x + "_" + y];
      if(_loc2_)
      {
         return _loc2_;
      }
      return null;
   }
}
