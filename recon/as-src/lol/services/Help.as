class lol.services.Help
{
   var HTTP;
   var _lessonsArr;
   var dispatchEvent;
   var status;
   static var sInstance;
   static var singleCreation;
   var loaded = false;
   function Help()
   {
      if(!lol.services.Help.singleCreation)
      {
         trace("Error: New Help error! Use getInstance method.");
      }
      else
      {
         this.init();
      }
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
   }
   function start()
   {
      if(!this.loaded)
      {
         this.loadXML();
      }
      else
      {
         this.dispatchEvent({type:"onLoad"});
      }
   }
   function loadXML()
   {
      this.HTTP = new lol.server.HTTPRequest();
      this.HTTP.addEventListener("onXML",this);
      this.HTTP.addEventListener("failed",this);
      var _loc2_ = lol.services.SSEmulator.getHelpXmlURL();
      this.HTTP.Send("",_loc2_);
   }
   function onXML(obj)
   {
      var _loc4_ = obj.data.idMap;
      this.HTTP.removeEventListener("onXML",this);
      this.HTTP.kill();
      this.HTTP = null;
      this._lessonsArr = new Array();
      var _loc3_ = 0;
      var _loc2_;
      while(_loc4_[_loc3_])
      {
         _loc2_ = new Object();
         _loc2_.title = _loc4_[_loc3_].attributes.title;
         _loc2_.active = _loc4_[_loc3_].attributes.active;
         _loc2_.id = _loc3_;
         this._lessonsArr.push(_loc2_);
         _loc3_ = _loc3_ + 1;
      }
      this.status = "loaded";
      this.loaded = true;
      this.dispatchEvent({type:"onLoad"});
   }
   function startHelp()
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("helpVideoLessons","globalCenter");
      _loc2_.content.lessonsArr = this.lessonsArr;
      _loc2_.content.curLesson = 0;
   }
   function failed(obj)
   {
   }
   function get lessonsArr()
   {
      return this._lessonsArr;
   }
   static function getInstance()
   {
      if(!lol.services.Help.sInstance)
      {
         lol.services.Help.singleCreation = true;
         lol.services.Help.sInstance = new lol.services.Help();
         lol.services.Help.singleCreation = false;
      }
      return lol.services.Help.sInstance;
   }
}
