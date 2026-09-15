class lol.core.SSettings
{
   var HTTPR;
   var base;
   var dispatchEvent;
   var host;
   var loaded;
   var pathArr;
   var port;
   var rdatatest;
   static var sInstance;
   static var singleCreation;
   static var ITEM_ICON = "item_icon";
   static var ITEM_ANIM = "item_anim";
   static var AVATAR_LIST = "avatar_list";
   static var AVATAR = "avatar";
   static var SPRITE = "sprite";
   static var GLOBALMAP = "globalmap";
   static var LOCATION_INFO = "location_info";
   static var LOCATION_LIB = "location_lib";
   static var MOB_ANIM = "mob_anim";
   static var MOB_INFO = "mob_info";
   static var CHAR_ANIM = "char_anim";
   static var CHAR_INFO = "char_info";
   static var TEXT = "text";
   static var SOUND = "sound";
   static var CSETTINGS_URL = "xmldocs/csettings_v1.xml";
   function SSettings()
   {
      if(lol.core.SSettings.singleCreation)
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
      if(!this.HTTPR)
      {
         this.HTTPR = new lol.server.HTTPRequest();
         this.HTTPR = new lol.server.HTTPRequest();
         this.HTTPR.addEventListener("onXML",this);
         this.HTTPR.addEventListener("failed",this);
         lol.core.SceneShifter.main.dPan.trace("start -> CSETTINGS_URL = " + lol.core.SSettings.CSETTINGS_URL);
         this.HTTPR.Send("",lol.core.SSettings.CSETTINGS_URL);
      }
   }
   function onXML(obj)
   {
      lol.services.SSEmulator.PATHTYPE = lol.services.SSEmulator.WEB;
      this.loaded = true;
      this.parse(obj.data);
      this.dispatchEvent({type:"onLoad"});
   }
   function failed()
   {
      lol.services.SSEmulator.PATHTYPE = lol.services.SSEmulator.LOCAL;
      this.host = _root.var_host;
      this.port = _root.var_port;
      this.loaded = true;
      this.dispatchEvent({type:"onLoad"});
   }
   function parse(doc)
   {
      var _loc3_ = doc.firstChild.childNodes;
      var _loc2_;
      for(var _loc4_ in _loc3_)
      {
         _loc2_ = _loc3_[_loc4_];
         if(_loc2_.nodeName == "gamesrv")
         {
            this.host = _loc2_.attributes.host;
            this.port = Number(_loc2_.attributes.port);
         }
         else if(_loc2_.nodeName == "debug")
         {
            lol.services.SSEmulator.DEBUG = _loc2_.attributes.value;
         }
         else if(_loc2_.nodeName == "resource")
         {
            this.parseResPaths(_loc2_);
         }
         else if(_loc2_.nodeName == "rdatatest")
         {
            this.rdatatest = new Object();
            this.rdatatest.title = _loc2_.attributes.title;
            this.rdatatest.body = _loc2_.childNodes.join("");
         }
      }
   }
   function parseResPaths(doc)
   {
      this.pathArr = new Array();
      var _loc3_ = doc.childNodes;
      this.base = doc.attributes.base;
      var _loc5_;
      var _loc4_;
      var _loc6_;
      var _loc2_;
      for(var _loc7_ in _loc3_)
      {
         _loc2_ = _loc3_[_loc7_];
         _loc5_ = mx.utils.XMLString.unescape(_loc2_.childNodes.join(""));
         _loc4_ = _loc2_.nodeName;
         _loc6_ = _loc2_.attributes.format;
         this.pathArr[_loc4_] = {path:_loc5_,format:_loc6_};
      }
   }
   function getPath(name)
   {
      return this.pathArr[name].path;
   }
   static function getInstance()
   {
      if(!lol.core.SSettings.sInstance)
      {
         lol.core.SSettings.singleCreation = true;
         lol.core.SSettings.sInstance = new lol.core.SSettings();
         lol.core.SSettings.singleCreation = false;
      }
      return lol.core.SSettings.sInstance;
   }
}
