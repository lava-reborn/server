class lol.utils.StringCollector
{
   var dispatchEvent;
   var stack;
   var status;
   var stringCollection;
   var timer;
   static var instance_;
   function StringCollector()
   {
      if(lol.utils.StringCollector.instance_ == null)
      {
         this.init();
      }
   }
   static function getInstance()
   {
      if(!lol.utils.StringCollector.instance_)
      {
         lol.utils.StringCollector.instance_ = new lol.utils.StringCollector();
      }
      return lol.utils.StringCollector.instance_;
   }
   function init()
   {
      this.stringCollection = new Array();
      lol.events.LEventDispatcher.initialize(this);
      this.stack = new Array();
   }
   function getString(id)
   {
      if(!(isNaN(id) || id == undefined || id == null))
      {
         if(!this.stringCollection[id])
         {
            this.addID(id);
            this.stringCollection[id] = 1;
         }
         else if(this.stringCollection[id] != 1)
         {
            return this.stringCollection[id];
         }
      }
      return null;
   }
   function addID(id)
   {
      if(!this.status)
      {
         this.status = true;
         this.timer = new lol.utils.Timeout(this,this.request,50,this.stack);
      }
      this.stack.push(id);
   }
   function request(arr)
   {
      this.status = false;
      this.stack = new Array();
      var _loc3_ = "<data>" + arr.join() + "</data>";
      var _loc5_ = new XML(_loc3_);
      var _loc2_ = new lol.server.HTTPRequest();
      _loc2_.addEventListener("onXML",this);
      _loc2_.addEventListener("failed",this);
      var _loc4_ = lol.services.SSEmulator.getStringURL();
      _loc2_.Send(_loc3_,_loc4_);
   }
   function onXML(obj)
   {
      this.parse(obj.data);
      obj.target.removeEventListener("onXML",this);
      obj.target.kill();
      lol.core.SceneShifter.main.dPan.loadingReport("ok. " + obj.target.url);
   }
   function parse(doc)
   {
      var _loc8_ = new Array();
      var _loc4_ = doc.firstChild.childNodes;
      var _loc2_;
      var _loc5_;
      var _loc6_;
      var _loc3_;
      for(var _loc7_ in _loc4_)
      {
         _loc2_ = Number(_loc4_[_loc7_].attributes.id);
         _loc5_ = _loc4_[_loc7_].childNodes.join("");
         _loc6_ = mx.utils.XMLString.unescape(_loc5_);
         _loc3_ = new lol.utils.SCString(_loc2_,_loc6_);
         this.stringCollection[_loc2_] = _loc3_;
         _loc8_.push(_loc3_);
      }
      this.dispatchEvent({type:"update",data:_loc8_});
   }
   function failed(obj)
   {
      lol.core.SceneShifter.main.dPan.loadingReport("error. " + obj.target.url);
      this.dispatchEvent({type:"failed"});
   }
   function requestAll()
   {
      var _loc2_ = new lol.server.HTTPRequest();
      _loc2_.addEventListener("onXML",this);
      _loc2_.addEventListener("failed",this);
      var _loc3_ = lol.services.SSEmulator.getStringURL();
      _loc2_.Send("",_loc3_ + "?all=1");
   }
}
