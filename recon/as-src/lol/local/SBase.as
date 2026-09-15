class lol.local.SBase
{
   var dispatchEvent;
   var itemDB;
   var locList;
   var localEntry;
   var modDB;
   static var sInstance;
   static var singleCreation;
   var count = 0;
   function SBase()
   {
      if(!lol.local.SBase.singleCreation)
      {
         trace("Error: New SBase error! Use getInstance method.");
      }
      else
      {
         lol.events.LEventDispatcher.initialize(this);
      }
   }
   function init()
   {
      this.localEntry = new lol.local.SourceObject(lol.services.SSEmulator.localPath,"index.xml",null);
      this.localEntry.addEventListener("onLoad",this,this.loadHandler);
      this.localEntry.loadList();
   }
   function loadHandler(obj)
   {
      var _loc5_ = this.localEntry.getList();
      var _loc3_ = _loc5_.getList();
      var _loc2_;
      for(var _loc4_ in _loc3_)
      {
         _loc2_ = lol.local.SourceObject(_loc3_[_loc4_]);
         _loc2_.addEventListener("onLoad",this,this.__loadHandler);
         _loc2_.loadList();
      }
   }
   function __loadHandler(obj)
   {
      var _loc2_ = obj.target;
      this.count += _loc2_.getList().length;
   }
   function createDB()
   {
      if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.LOCAL)
      {
         this.initializeLocalItemDB();
      }
      else if(lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         this.initializeWebItemDB();
      }
   }
   function initializeLocalItemDB()
   {
      this.itemDB = new lol.local.SDBList(lol.services.SSEmulator.localPath + "database/objects.xml");
      this.itemDB.addEventListener("onLoad",this,this.initializeLocalMobDB);
      this.itemDB.addEventListener("failed",this,this.initializeLocalMobDB);
   }
   function initializeLocalMobDB()
   {
      this.modDB = new lol.local.SDBList(lol.services.SSEmulator.localPath + "database/mobs.xml");
      this.modDB.addEventListener("onLoad",this,this.initializeLocalLocationListDB);
      this.modDB.addEventListener("failed",this,this.initializeLocalLocationListDB);
   }
   function initializeLocalLocationListDB()
   {
      this.locList = new lol.local.SourceObject(lol.services.SSEmulator.localPath,"xml/loc_defs.xml","");
      this.locList.addEventListener("onLoad",this,this.initializeStringCollector);
      this.locList.addEventListener("failed",this,this.initializeStringCollector);
      this.locList.loadList();
   }
   function initializeWebItemDB()
   {
      this.itemDB = new lol.local.SDBList(lol.core.SSettings.getInstance().base + "/database/objects.xml?random=" + lol.services.SSEmulator.getRandom());
      this.itemDB.addEventListener("onLoad",this,this.initializeWebMobDB);
      this.itemDB.addEventListener("failed",this,this.initializeWebMobDB);
   }
   function initializeWebMobDB()
   {
      this.modDB = new lol.local.SDBList(lol.core.SSettings.getInstance().base + "/database/mobs.xml?random=" + lol.services.SSEmulator.getRandom());
      this.modDB.addEventListener("onLoad",this,this.initializeWebLocationListDB);
      this.modDB.addEventListener("failed",this,this.initializeWebLocationListDB);
   }
   function initializeWebLocationListDB()
   {
      this.locList = new lol.local.SourceObject(lol.core.SSettings.getInstance().base,"/xml/loc_defs.xml?random=" + lol.services.SSEmulator.getRandom(),"");
      this.locList.addEventListener("onLoad",this,this.initializeStringCollector);
      this.locList.addEventListener("failed",this,this.initializeStringCollector);
      this.locList.loadList();
   }
   function initializeStringCollector()
   {
      var _loc2_ = lol.utils.StringCollector.getInstance();
      _loc2_.addEventListener("update",this,this.initializeLocationNames);
      _loc2_.addEventListener("failed",this,this.initializeLocationNames);
      _loc2_.requestAll();
   }
   function initializeLocationNames()
   {
      lol.utils.GetLocName.instance.addEventListener("onLoad",this,this.dispatchEnding);
      lol.utils.GetLocName.instance.addEventListener("failed",this,this.dispatchEnding);
      lol.utils.GetLocName.instance.loadXML();
   }
   function dispatchEnding()
   {
      this.dispatchEvent({type:"onLoad"});
   }
   function getItem(typeID)
   {
      return this.itemDB.getItem(typeID);
   }
   function getItemName(typeID)
   {
      return this.itemDB.getName(typeID);
   }
   function getMob(typeID)
   {
      return this.modDB.getItem(typeID);
   }
   function getMobName(typeID)
   {
      return this.modDB.getName(typeID);
   }
   function getLocDef(name)
   {
      return this.locList.getList().getObject(name);
   }
   static function getInstance()
   {
      if(!lol.local.SBase.sInstance)
      {
         lol.local.SBase.singleCreation = true;
         lol.local.SBase.sInstance = new lol.local.SBase();
         lol.local.SBase.singleCreation = false;
      }
      return lol.local.SBase.sInstance;
   }
}
