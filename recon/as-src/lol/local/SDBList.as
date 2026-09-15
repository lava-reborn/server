class lol.local.SDBList
{
   var _list;
   var _path;
   var dispatchEvent;
   var httpR;
   function SDBList(path)
   {
      this._path = path;
      lol.events.LEventDispatcher.initialize(this);
      this.init();
   }
   function init()
   {
      if(this._path != undefined)
      {
         this.httpR = new lol.server.HTTPRequest();
         this.httpR.addEventListener("onXML",this,this.loadHandler);
         this.httpR.addEventListener("failed",this,this.loadErrorHandler);
         this.httpR.Send("",this._path);
      }
   }
   function loadHandler(obj)
   {
      this.httpR.removeEventListener("onXML",this,this.loadHandler);
      var _loc2_ = obj.data;
      this.parse(_loc2_);
      this.dispatchEvent({type:"onLoad"});
      lol.core.SceneShifter.main.dPan.loadingReport("ok... " + this._path);
   }
   function loadErrorHandler()
   {
      lol.core.SceneShifter.main.dPan.loadingReport("error. " + this._path);
      this.dispatchEvent({type:"failed"});
   }
   function parse(doc)
   {
      this._list = new Array();
      var _loc8_ = doc.firstChild.childNodes;
      var _loc3_ = 0;
      var _loc2_;
      var _loc4_;
      var _loc6_;
      var _loc5_;
      var _loc7_;
      while(_loc3_ < _loc8_.length)
      {
         _loc2_ = _loc8_[_loc3_];
         _loc4_ = Number(_loc2_.attributes.type_id);
         _loc6_ = Number(_loc2_.attributes.root_type_id);
         _loc5_ = _loc2_.attributes.name;
         _loc7_ = _loc2_.attributes.resource;
         this._list[_loc4_] = new lol.local.SDBItem(_loc4_,_loc6_,_loc5_,_loc7_);
         _loc3_ = _loc3_ + 1;
      }
   }
   function getItem(typeID)
   {
      return this._list[typeID];
   }
   function getName(typeID)
   {
      return lol.local.SDBItem(this._list[typeID]).name;
   }
}
