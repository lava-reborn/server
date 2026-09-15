class lol.server.HTTPRequest
{
   var addEventListener;
   var connector;
   var dispatchEvent;
   var myXML;
   var onLoad;
   var removeEventListener;
   var spt;
   var spt_int;
   function HTTPRequest()
   {
      this.init();
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.connector = new XML();
      this.connector.ignoreWhite = true;
      this.connector.onLoad = mx.utils.Delegate.create(this,this.onLoadHTTP);
      this.addEventListener("onLoad",this);
   }
   function onLoadHTTP(success)
   {
      if(success)
      {
         this.onXML(this.connector);
      }
      else
      {
         this.requestFailed();
      }
      this.dispatchEvent({type:"onLoad",success:success});
   }
   function onXML(doc)
   {
      this.dispatchEvent({type:"onXML",data:doc});
   }
   function requestFailed()
   {
      var _loc2_ = "failed";
      this.dispatchEvent({type:_loc2_});
   }
   function Send()
   {
      var _loc3_;
      var _loc4_;
      if(typeof arguments[0] == "object")
      {
         _loc3_ = arguments[0].data;
         _loc4_ = arguments[0].url;
      }
      else if(typeof arguments[0] == "string")
      {
         _loc3_ = arguments[0];
         _loc4_ = arguments[1];
      }
      this.myXML = new XML(_loc3_);
      this.myXML.sendAndLoad(_loc4_,this.connector);
      delete this.myXML;
      this.dispatchEvent({type:"onSend",data:_loc3_});
   }
   static function childsToArray(node)
   {
      var _loc2_ = new Array();
      var _loc1_ = node.childNodes;
      for(var _loc3_ in _loc1_)
      {
         _loc2_[_loc1_[_loc3_].nodeName] = _loc1_[_loc3_];
      }
      return _loc2_;
   }
   static function parseChilds(doc)
   {
      var _loc5_ = new Array();
      var _loc3_ = doc.childNodes;
      var _loc1_;
      var _loc2_;
      var _loc4_;
      for(var _loc6_ in _loc3_)
      {
         _loc1_ = _loc3_[_loc6_];
         _loc2_ = lol.server.HTTPRequest.attributesToObject(_loc1_);
         _loc4_ = _loc1_.attributes.id;
         _loc5_.push(_loc2_);
      }
      return _loc5_;
   }
   static function attributesToObject(node)
   {
      var _loc2_ = new Object();
      for(var _loc3_ in node.attributes)
      {
         _loc2_[_loc3_] = node.attributes[_loc3_];
      }
      return _loc2_;
   }
   function kill()
   {
      this.removeEventListener("onLoad",this);
      this.connector.onLoad.target = null;
      this.connector.onLoad.func = null;
      delete this.connector.onLoad;
      delete this.onLoad;
      delete this.connector;
      delete this.myXML;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("HTTP" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
