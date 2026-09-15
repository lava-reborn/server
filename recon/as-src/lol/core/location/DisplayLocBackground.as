class lol.core.location.DisplayLocBackground extends MovieClip
{
   var backgroundBM;
   function DisplayLocBackground()
   {
      super();
   }
   function createBack(locInfo)
   {
      this.createBackBM();
      var _loc3_;
      var _loc4_;
      if(locInfo.back.fx == "water")
      {
         _loc3_ = this.getBackBM(locInfo);
         _loc4_ = lol.utils.MCFabric.create(lol.fx.Water0,this,"water_mc",0,[_loc3_]);
      }
      else
      {
         this.fillBackground(locInfo);
      }
      this.drawBGDecor(locInfo.bgDecorations,locInfo.libraryID);
      this.drawZones(locInfo);
   }
   function createBackBM()
   {
      var _loc2_ = lol.core.Master.getInstance().currentLocation;
      var _loc4_ = _loc2_.locationGrid.gridW * lol.core.location.LocationGrid.cellW;
      var _loc3_ = _loc2_.locationGrid.gridH * lol.core.location.LocationGrid.cellH;
      this.backgroundBM = new flash.display.BitmapData(_loc4_,_loc3_,true,0);
      if(this.backgroundBM != undefined)
      {
         this.attachBitmap(this.backgroundBM,1);
      }
   }
   function getBackBM(locInfo)
   {
      var _loc1_ = locInfo.back;
      var _loc2_ = _loc1_.id;
      var _loc4_ = _loc1_.resType;
      var _loc3_;
      var _loc6_;
      var _loc5_;
      if(_loc4_ == "ext")
      {
         _loc3_ = lol.display.SourceLibrary.getSource(_loc2_).getBitmap();
      }
      else
      {
         _loc6_ = locInfo.libraryID;
         _loc5_ = lol.display.SourceLibrary.getSource(_loc6_);
         _loc3_ = _loc5_.getFromLib(_loc2_);
      }
      return _loc3_;
   }
   function fillBackground(locInfo)
   {
      var _loc6_ = this.getBackBM(locInfo);
      var _loc5_ = _loc6_.width;
      var _loc4_ = _loc6_.height;
      var _loc3_ = 0;
      var _loc2_;
      while(_loc3_ < this.backgroundBM.width)
      {
         _loc2_ = 0;
         while(_loc2_ < this.backgroundBM.height)
         {
            this.backgroundBM.copyPixels(_loc6_,new flash.geom.Rectangle(0,0,_loc5_,_loc4_),new flash.geom.Point(_loc3_,_loc2_));
            _loc2_ += _loc4_;
         }
         _loc3_ += _loc5_;
      }
   }
   function drawBGDecor(arr, libID)
   {
      var _loc8_ = new flash.geom.Matrix();
      var _loc2_ = 0;
      var _loc9_;
      var _loc10_;
      var _loc11_;
      var _loc7_;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      while(_loc2_ < arr.length)
      {
         _loc9_ = lol.display.SourceLibrary.getSource(libID);
         _loc10_ = lol.core.Master.getInstance().currentLocation;
         _loc11_ = _loc10_.getCellFromGrid(arr[_loc2_].point.x,arr[_loc2_].point.y);
         _loc7_ = arr[_loc2_].resID;
         _loc6_ = arr[_loc2_].dx;
         _loc5_ = arr[_loc2_].dy;
         if(arr[_loc2_].resType == "ext")
         {
            _loc4_ = lol.display.SourceLibrary.getSource(_loc7_).getBitmap();
         }
         else
         {
            _loc4_ = _loc9_.getFromLib(_loc7_);
         }
         _loc8_.translate(_loc6_,_loc5_);
         this.backgroundBM.draw(_loc4_,_loc8_);
         _loc8_.translate(- _loc6_,- _loc5_);
         _loc2_ = _loc2_ + 1;
      }
      false;
   }
   function drawZones()
   {
      var _loc8_ = lol.core.Master.getInstance().currentLocation.locationGrid.zone_arr;
      var _loc11_ = this.attachMovie("zoneHex","z",this.getNextHighestDepth());
      var _loc7_ = new flash.geom.Matrix();
      var _loc3_ = 0;
      var _loc2_;
      var _loc10_;
      var _loc9_;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      while(_loc3_ < _loc8_.length)
      {
         _loc2_ = _loc8_[_loc3_];
         _loc10_ = _loc2_.rx;
         _loc9_ = _loc2_.ry;
         _loc6_ = lol.core.location.LocDeclaration.abstractToReal({x:_loc2_.rx,y:_loc2_.ry});
         _loc5_ = 5 * Math.round(_loc6_.x / 5);
         _loc4_ = 5 * Math.round(_loc6_.y / 5);
         _loc7_.translate(_loc5_,_loc4_);
         this.backgroundBM.draw(_loc11_,_loc7_);
         _loc7_.translate(- _loc5_,- _loc4_);
         _loc3_ = _loc3_ + 1;
      }
      false;
      _loc11_.removeMovieClip();
   }
}
