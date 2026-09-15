class lol.core.location.LocGen
{
   var HR;
   var addEventListener;
   var dispatchEvent;
   var generatedLoc;
   var geoID;
   var locID;
   var locPreloader;
   var lsLoader;
   var removeEventListener;
   function LocGen()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.lsLoader = new lol.core.location.LocSourceLoader();
      this.lsLoader.addEventListener("locLoaded",this);
      this.lsLoader.addEventListener("onLoadProgress",this);
   }
   function loadLocDescription(loc_id)
   {
      this.killHR();
      this.locID = loc_id;
      var _loc2_ = lol.services.SSEmulator.getLocDescription(this.locID);
      this.HR = new lol.server.HTTPRequest();
      this.HR.addEventListener("onXML",this);
      this.HR.addEventListener("failed",this,this.loadLocFailed);
      this.HR.Send("",_loc2_);
      this.openPreloader();
      this.locPreloader.setTitle("Подождите, идет загрузка");
      this.generatedLoc = new lol.core.location.Location();
   }
   function onXML(obj)
   {
      var _loc2_ = obj.data;
      this.locationInfo(_loc2_);
      this.killHR();
   }
   function loadLocFailed(obj)
   {
      lol.core.SceneShifter.main.dPan.loadingReport("loadLocDescription FAILED!)");
   }
   function killHR()
   {
      this.HR.removeEventListener("onXML",this);
      this.HR.kill();
      this.HR = null;
   }
   function locationInfo(doc)
   {
      var _loc2_ = lol.core.location.LDParser.parseLD(doc);
      _loc2_.locID = this.locID;
      _loc2_.geoID = this.geoID;
      this.generatedLoc.locInfo = _loc2_;
      this.generatedLoc.locationGrid = new lol.core.location.LocationGrid(_loc2_.width,_loc2_.height);
      this.generatedLoc.locationGrid.setObstacles(_loc2_.obstacles);
      this.generatedLoc.locationGrid.setZones(_loc2_.zones);
      this.loadSources(_loc2_);
   }
   function loadSources(locInfo)
   {
      if(lol.core.Master.getInstance().playerIntercepted())
      {
         this.locPreloader.setTitle("Внимание! На Вас напали в локации\r \"" + locInfo.locationName + "\"");
      }
      else
      {
         this.locPreloader.setTitle("Переход в локацию\r \"" + locInfo.locationName + "\"");
      }
      lol.core.SceneShifter.newLocationGameHelpMessage(locInfo.locationName);
      this.lsLoader.loadSources(locInfo);
   }
   function openPreloader()
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("loadLoc","center");
      this.locPreloader = _loc2_.content;
      this.addEventListener("onLoadProgress",this.locPreloader);
   }
   function onLoadProgress(obj)
   {
      var _loc4_ = obj.bytesLoaded;
      var _loc2_ = obj.bytesTotal;
      this.dispatchEvent({type:"onLoadProgress",bytesLoaded:_loc4_,bytesTotal:_loc2_});
   }
   function locLoaded(obj)
   {
      this.removeEventListener("onLoadProgress",this.locPreloader);
      lol.core.SceneShifter.closeWindow("loadLoc");
      this.dispatchEvent({type:"locLoaded"});
   }
   function getGL()
   {
      return this.generatedLoc;
   }
   function setGL(loc)
   {
      this.generatedLoc = loc;
   }
}
