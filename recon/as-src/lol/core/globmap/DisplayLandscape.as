class lol.core.globmap.DisplayLandscape
{
   var dispatchEvent;
   var gridCellArr;
   var grid_mc;
   var land_mc;
   var mapCellArr;
   var prevMapScale;
   static var SMALL = "small";
   static var FULL = "full";
   var mapScaleType = lol.core.globmap.DisplayLandscape.SMALL;
   var mapScale = 1;
   var cellSize = 32;
   var locationSize = 8;
   var updateAllow = false;
   function DisplayLandscape()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.mapCellArr = new Array();
      this.gridCellArr = new Array();
   }
   function drawArea(x, y, centerPers)
   {
      if(this.prevMapScale != this.mapScale)
      {
         this.clearArea();
         this.prevMapScale = this.mapScale;
      }
      var _loc10_ = Math.floor(this.mapScale * x / this.cellSize);
      var _loc9_ = Math.floor(this.mapScale * y / this.cellSize);
      var _loc12_ = lol.core.SceneShifter.gmapScreen.getFrameSize();
      var _loc11_ = Math.floor(0.5 * _loc12_.width / this.cellSize) + 1;
      var _loc13_ = Math.floor(0.5 * _loc12_.height / this.cellSize) + 1;
      var _loc8_ = _loc10_ - _loc11_;
      var _loc7_ = _loc10_ + _loc11_ + 1;
      var _loc6_ = _loc9_ - _loc13_;
      var _loc5_ = _loc9_ + _loc13_ + 1;
      var _loc4_;
      var _loc3_ = _loc8_;
      var _loc2_;
      while(_loc3_ <= _loc7_)
      {
         _loc4_ = "cell" + String(_loc3_);
         _loc2_ = _loc6_;
         while(_loc2_ <= _loc5_)
         {
            if(!this.land_mc[_loc4_ + String(_loc2_)])
            {
               this.createCell(_loc3_,_loc2_);
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc3_ = _loc3_ + 1;
      }
      var _loc16_ = (_loc10_ - 2) * this.cellSize;
      var _loc14_ = (_loc9_ - 2) * this.cellSize;
      var _loc17_ = 5 * this.cellSize;
      var _loc15_ = 5 * this.cellSize;
      lol.core.SceneShifter.gmapScreen.globalMapFrame.setScrollArea(_loc16_,_loc14_,_loc17_,_loc15_);
   }
   function createCell(ix, jy)
   {
      var _loc6_ = lol.services.SSEmulator.getGMTURL(ix,jy,this.mapScaleType);
      var _loc5_ = this.land_mc.getNextHighestDepth();
      var _loc2_ = lol.display.DisplaySprite.create(this.land_mc,"cell" + String(ix) + String(jy),_loc5_);
      _loc2_.addEventListener("completed",this,this.onLoadCell);
      _loc2_.display("gmcell" + ix + jy + this.cellSize,_loc6_);
      this.mapCellArr.push(_loc2_);
      _loc2_._x = ix * this.cellSize;
      _loc2_._y = jy * this.cellSize;
      if(_loc2_._width < this.cellSize || _loc2_._width < this.cellSize)
      {
         _loc2_._width = _loc2_._height = this.cellSize;
      }
      this.drawCellBorder(_loc2_._x,_loc2_._y);
   }
   function onLoadCell(obj)
   {
      var _loc2_ = obj.target;
      _loc2_.removeEventListener("completed",this,this.onLoadCell);
      if(_loc2_._width < this.cellSize || _loc2_._width < this.cellSize)
      {
         _loc2_._width = _loc2_._height = this.cellSize;
      }
   }
   function updateLandPosition()
   {
      this.dispatchEvent({type:"build"});
   }
   function drawCellBorder(x, y)
   {
      var _loc5_ = this.grid_mc.getNextHighestDepth();
      var _loc3_ = this.grid_mc.createEmptyMovieClip("c" + _loc5_,_loc5_);
      this.gridCellArr.push(_loc3_);
      _loc3_._x = x;
      _loc3_._y = y;
      _loc3_.lineStyle(1,0,30);
      _loc3_.moveTo(0,this.cellSize);
      _loc3_.lineTo(0,0);
      _loc3_.lineTo(this.cellSize,0);
      var _loc4_ = Math.floor(this.cellSize / this.locationSize);
      _loc3_.lineStyle(1,0,10);
      var _loc2_ = 1;
      while(_loc2_ < _loc4_)
      {
         _loc3_.moveTo(_loc2_ * this.locationSize,0);
         _loc3_.lineTo(_loc2_ * this.locationSize,this.cellSize);
         _loc3_.moveTo(0,_loc2_ * this.locationSize);
         _loc3_.lineTo(this.cellSize,_loc2_ * this.locationSize);
         _loc2_ = _loc2_ + 1;
      }
      var _loc7_ = new flash.display.BitmapData(_loc3_._width,_loc3_._height,true,0);
      var _loc6_ = this.grid_mc.createEmptyMovieClip("bc" + _loc5_,_loc5_ + 1);
      _loc6_.attachBitmap(_loc7_,0);
      _loc7_.draw(_loc3_);
      _loc6_._x = x;
      _loc6_._y = y;
      _loc3_.removeMovieClip();
      this.updateLandPosition();
   }
   function setScale(type)
   {
      this.mapScaleType = type;
      if(type == lol.core.globmap.DisplayLandscape.FULL)
      {
         this.mapScale = 8;
         this.cellSize = 256;
      }
      else if(type == lol.core.globmap.DisplayLandscape.SMALL)
      {
         this.mapScale = 1;
         this.cellSize = 256;
      }
   }
   function clearArea()
   {
      for(var _loc2_ in this.mapCellArr)
      {
         if(typeof this.mapCellArr[_loc2_] == "movieclip")
         {
            this.mapCellArr[_loc2_].removeEventListener("completed",this,this.onLoadCell);
            this.mapCellArr[_loc2_].destroy();
            this.mapCellArr[_loc2_].removeMovieClip();
            this.mapCellArr[_loc2_] = null;
         }
      }
      for(var _loc3_ in this.gridCellArr)
      {
         if(typeof this.gridCellArr[_loc3_] == "movieclip")
         {
            this.gridCellArr[_loc3_].removeMovieClip();
            this.gridCellArr[_loc3_] = null;
         }
      }
      var _loc4_ = this.grid_mc._parent;
      this.grid_mc.removeMovieClip();
      this.grid_mc = _loc4_.createEmptyMovieClip("grid_mc",4);
      this.mapCellArr = new Array();
      this.gridCellArr = new Array();
   }
   function kill()
   {
      this.clearArea();
      false;
   }
}
