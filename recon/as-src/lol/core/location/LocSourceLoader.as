class lol.core.location.LocSourceLoader
{
   var dispatchEvent;
   var libSrc;
   var loadStatusList;
   var loadedSourceList;
   var sourceList;
   var count = 0;
   function LocSourceLoader()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.loadedSourceList = new Array();
   }
   function loadSources(locInfo)
   {
      this.loadStatusList = new Array();
      this.clearList();
      this.loadSource(locInfo.libraryID,lol.services.SSEmulator.getLocLibraryURL(locInfo.libraryID));
      var _loc4_ = 0;
      var _loc3_;
      while(_loc4_ < locInfo.sprites.length)
      {
         _loc3_ = locInfo.sprites[_loc4_];
         if(_loc3_.resType == "ext")
         {
            this.loadSource(_loc3_.resID,lol.services.SSEmulator.getSpriteURL("sprite",_loc3_.resID));
         }
         _loc4_ = _loc4_ + 1;
      }
      _loc4_ = 0;
      var _loc2_;
      while(_loc4_ < locInfo.bgDecorations.length)
      {
         _loc2_ = locInfo.bgDecorations[_loc4_];
         if(_loc2_.resType == "ext")
         {
            this.loadSource(_loc2_.resID,lol.services.SSEmulator.getSpriteURL("sprite",_loc2_.resID));
         }
         _loc4_ = _loc4_ + 1;
      }
      if(locInfo.back.resType == "ext")
      {
         this.loadSource(locInfo.back.id,lol.services.SSEmulator.getSpriteURL("background",locInfo.back.id));
      }
      if(this.sourceList.length == 0)
      {
         this.dispatchEvent({type:"locLoaded"});
      }
   }
   function loadSource(name, url)
   {
      var _loc2_ = lol.display.SourceLibrary.getSource(name);
      if(_loc2_.status == null)
      {
         _loc2_.addEventListener("onLoadSource",this);
         _loc2_.addEventListener("onLoadError",this);
         this.sourceList.push(_loc2_);
         if(this.libSrc.status != "loading")
         {
            _loc2_.addEventListener("onLoadProgress",this);
            _loc2_.loadSource(url);
         }
      }
   }
   function onLoadSource(obj)
   {
      var _loc2_ = obj.target;
      _loc2_.removeEventListener("onLoadSource",this);
      _loc2_.removeEventListener("onLoadProgress",this);
      _loc2_.removeEventListener("onLoadError",this);
      this.loadStatusList.push("Loaded " + _loc2_.sourceName + "  " + _loc2_.sourceURL);
      this.loadedSourceList[_loc2_.sourceName] = _loc2_;
      this.checkLoad();
   }
   function clearList()
   {
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.sourceList.length)
      {
         _loc3_ = this.sourceList[_loc2_];
         _loc3_.removeEventListener("onLoadSource",this);
         _loc3_.removeEventListener("onLoadProgress",this);
         _loc2_ = _loc2_ + 1;
      }
      this.sourceList = new Array();
      this.count = 0;
   }
   function onLoadError(obj)
   {
      var _loc2_ = obj.target;
      this.loadStatusList.push("!!! Error loading " + _loc2_.sourceName + "  " + _loc2_.sourceURL);
      this.checkLoad();
   }
   function onLoadProgress(obj)
   {
      var _loc4_ = obj.bytesLoaded;
      var _loc2_ = obj.bytesTotal;
      this.dispatchEvent({type:"onLoadProgress",bytesLoaded:_loc4_,bytesTotal:_loc2_});
   }
   function checkLoad()
   {
      this.count = this.count + 1;
      if(this.count == this.sourceList.length)
      {
         this.dispatchEvent({type:"locLoaded",list:this.loadStatusList});
         this.clearList();
      }
   }
   function unloadSources(locInfo, excludedLocInfo)
   {
      this.unloadAllSources(locInfo);
   }
   function unloadAllSources(locInfo)
   {
      var _loc2_;
      for(var _loc4_ in this.loadedSourceList)
      {
         _loc2_ = _loc4_;
         if(!this.exist(_loc2_,locInfo))
         {
            this.unloadSource(_loc4_);
            this.loadedSourceList[_loc4_] = null;
         }
      }
   }
   function exist(name, locInfo)
   {
      if(name == locInfo.libraryID)
      {
         return true;
      }
      if(locInfo.back.resType == "ext" && locInfo.back.id == name)
      {
         return true;
      }
      var _loc1_ = 0;
      var _loc4_;
      while(_loc1_ < locInfo.sprites.length)
      {
         _loc4_ = locInfo.sprites[_loc1_];
         if(_loc4_.resType == "ext" && _loc4_.resID == name)
         {
            return true;
         }
         _loc1_ = _loc1_ + 1;
      }
      _loc1_ = 0;
      var _loc3_;
      while(_loc1_ < locInfo.bgDecorations.length)
      {
         _loc3_ = locInfo.bgDecorations[_loc1_];
         if(_loc3_.resType == "ext" && _loc3_.resID == name)
         {
            return true;
         }
         _loc1_ = _loc1_ + 1;
      }
      return false;
   }
   function unloadSource(name)
   {
      lol.display.SourceLibrary.clearSource(name);
   }
}
