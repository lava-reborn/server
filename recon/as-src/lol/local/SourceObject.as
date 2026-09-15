class lol.local.SourceObject
{
   var _hash;
   var _name;
   var _path;
   var _sList;
   var dispatchEvent;
   var httpR;
   function SourceObject(sPath, sName, sHash)
   {
      this._path = sPath;
      this._name = sName;
      this._hash = sHash;
      lol.events.LEventDispatcher.initialize(this);
   }
   function get name()
   {
      return this._name;
   }
   function get hash()
   {
      return this._hash;
   }
   function setSList(sl)
   {
      this._sList = sl;
   }
   function getList()
   {
      return this._sList;
   }
   function toString()
   {
      return this._name + ":" + this.hash;
   }
   function loadList()
   {
      this.httpR = new lol.server.HTTPRequest();
      this.httpR.addEventListener("onXML",this,this.loadHandler);
      this.httpR.addEventListener("failed",this,this.errorHandler);
      this.httpR.Send("",this._path + this._name);
   }
   function loadHandler(obj)
   {
      this.httpR.removeEventListener("onXML",this,this.loadHandler);
      var _loc3_ = obj.data;
      var _loc2_ = new lol.local.SourceList(_loc3_.firstChild,this._path);
      this.setSList(_loc2_);
      lol.core.SceneShifter.main.dPan.loadingReport("ok. " + this._path + this._name);
      this.dispatchEvent({type:"onLoad"});
   }
   function errorHandler()
   {
      lol.core.SceneShifter.main.dPan.loadingReport("error. " + this._path + this._name);
      this.dispatchEvent({type:"failed"});
   }
}
