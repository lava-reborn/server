class lol.core.location.LocBuilder
{
   var bg_mc;
   var busy_arr;
   var core_mc;
   var frHexMC;
   var frontBM;
   var objectList;
   var obstBM;
   var obstHexMC;
   var path_arr;
   var spt;
   var spt_int;
   var target;
   var reservedDepthsNum = 10;
   function LocBuilder(targ)
   {
      this.target = targ;
      this.target.addEventListener("enterFrame",this);
      this.core_mc = this.target.core_mc;
      this.bg_mc = this.target.bg_mc;
      this.objectList = this.target.displayList;
   }
   function buildScene()
   {
      var _loc5_ = lol.core.Master.getInstance().currentLocation.locInfo;
      var _loc6_ = _loc5_.bgID;
      var _loc4_ = _loc5_.libraryID;
      var _loc3_ = this.currentLocation.locInfo.sprites;
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         this.buildScenery(_loc4_,_loc3_[_loc2_],_loc2_);
         _loc2_ = _loc2_ + 1;
      }
      this.bg_mc.createBack(_loc5_);
   }
   function buildScenery(libID, obj, i)
   {
      var _loc6_ = this.currentLocation.getCellFromGrid(obj.point.x,obj.point.y);
      var _loc5_ = this.core_mc.getNextHighestDepth();
      var _loc4_;
      if(obj.resType == "lib")
      {
         _loc4_ = lol.display.DisplaySprite.create(this.core_mc,"el" + _loc5_,_loc5_);
      }
      else
      {
         _loc4_ = lol.display.AnimationSprite.create(this.core_mc,"el" + _loc5_,_loc5_);
      }
      this.target.placeObject(_loc4_,_loc6_.rx,_loc6_.ry);
      _loc4_._x += obj.resDX;
      _loc4_._y += obj.resDY;
      _loc6_.inCell(_loc4_);
      var _loc7_ = "lib/out/" + obj.resID + ".png";
      if(obj.resType == "lib")
      {
         _loc4_.displayLibrary(libID,obj.resID);
      }
      else
      {
         _loc4_.display(obj.resID,lol.services.SSEmulator.getSpriteURL("sprite",obj.resID));
      }
      var _loc3_ = new lol.core.location.SceneObject("static");
      _loc3_.sprite = _loc4_;
      _loc3_.resID = obj.resID;
      _loc3_.front = obj.front_arr;
      _loc3_.point = obj.point;
      _loc3_.resDX = obj.resDX;
      _loc3_.resDY = obj.resDY;
      _loc3_.type = "static";
      _loc3_.minD = 1;
      this.objectList.push(_loc3_);
      return _loc4_;
   }
   function createFrontHex()
   {
      this.frHexMC.removeMovieClip();
      this.frHexMC = this.target.helpers_mc.createEmptyMovieClip("frHexMC",this.target.helpers_mc.getNextHighestDepth());
      var _loc13_ = lol.core.Master.getInstance().currentLocation;
      var _loc15_ = _loc13_.locationGrid.gridW * lol.core.location.LocationGrid.cellW;
      var _loc14_ = _loc13_.locationGrid.gridH * lol.core.location.LocationGrid.cellH;
      this.frontBM = new flash.display.BitmapData(_loc15_,_loc14_,true,0);
      this.frHexMC.attachBitmap(this.frontBM,1);
      var _loc10_ = this.target.helpers_mc.attachMovie("obstPathHex","hex_mc",this.target.helpers_mc.getNextHighestDepth());
      _loc10_.createTextField("res_txt",10,-10,-10,60,20);
      _loc10_.res_txt.textColor = 16777215;
      var _loc9_ = 0;
      var _loc4_;
      var _loc3_;
      var _loc12_;
      var _loc11_;
      var _loc2_;
      var _loc6_;
      var _loc8_;
      var _loc7_;
      var _loc5_;
      while(_loc9_ < this.objectList.length)
      {
         _loc4_ = this.objectList[_loc9_];
         if(_loc4_.type != "dynamic")
         {
            _loc3_ = 0;
            while(_loc3_ < _loc4_.front_arr.length)
            {
               _loc12_ = _loc4_.front_arr[_loc3_].x;
               _loc11_ = _loc4_.front_arr[_loc3_].y;
               _loc2_ = this.target.getCellFromGrid(_loc12_,_loc11_);
               _loc10_.res_txt.text = _loc2_.gx + ":" + _loc2_.gy;
               _loc6_ = lol.core.location.LocDeclaration.abstractToReal({x:_loc2_.rx,y:_loc2_.ry});
               _loc8_ = 5 * Math.round(_loc6_.x / 5);
               _loc7_ = 5 * Math.round(_loc6_.y / 5);
               _loc5_ = new flash.geom.Matrix();
               _loc5_.translate(_loc8_,_loc7_);
               this.frontBM.draw(_loc10_,_loc5_);
               _loc3_ = _loc3_ + 1;
            }
         }
         _loc9_ = _loc9_ + 1;
      }
      _loc10_.removeMovieClip();
      this.frHexMC._alpha = 50;
   }
   function clearFronts()
   {
      this.frontBM.dispose();
      this.frontBM = null;
      this.frHexMC.removeMovieClip();
   }
   function showObstacles()
   {
      this.obstHexMC.removeMovieClip();
      this.obstHexMC = this.target.helpers_mc.createEmptyMovieClip("obstHexMC",this.target.helpers_mc.getNextHighestDepth());
      var _loc12_ = lol.core.Master.getInstance().currentLocation;
      var _loc14_ = _loc12_.locationGrid.gridW * lol.core.location.LocationGrid.cellW;
      var _loc13_ = _loc12_.locationGrid.gridH * lol.core.location.LocationGrid.cellH;
      this.obstBM = new flash.display.BitmapData(_loc14_,_loc13_,true,0);
      this.obstHexMC.attachBitmap(this.obstBM,1);
      var _loc8_ = this.target.helpers_mc.attachMovie("obstHex","hex_mc",this.target.helpers_mc.getNextHighestDepth());
      _loc8_.createTextField("res_txt",10,-10,-10,60,20);
      _loc8_.res_txt.textColor = 16777215;
      var _loc9_ = _loc12_.locationGrid.obstacle_arr;
      var _loc3_ = 0;
      var _loc2_;
      var _loc5_;
      var _loc7_;
      var _loc6_;
      var _loc4_;
      while(_loc3_ < _loc9_.length)
      {
         _loc2_ = _loc9_[_loc3_];
         _loc8_.res_txt.text = _loc2_.gx + ":" + _loc2_.gy;
         _loc5_ = lol.core.location.LocDeclaration.abstractToReal({x:_loc2_.rx,y:_loc2_.ry});
         _loc7_ = 5 * Math.round(_loc5_.x / 5);
         _loc6_ = 5 * Math.round(_loc5_.y / 5);
         _loc4_ = new flash.geom.Matrix();
         _loc4_.translate(_loc7_,_loc6_);
         this.obstBM.draw(_loc8_,_loc4_);
         _loc3_ = _loc3_ + 1;
      }
      this.obstHexMC._alpha = 50;
      _loc8_.removeMovieClip();
   }
   function clearObstacles()
   {
      this.obstBM.dispose();
      this.obstBM = null;
      this.obstHexMC.removeMovieClip();
   }
   function buildHex(link, cell, targ)
   {
      var _loc9_ = cell.rx;
      var _loc8_ = cell.ry;
      var _loc4_ = lol.core.location.LocDeclaration.abstractToReal({x:cell.rx,y:cell.ry});
      var _loc3_ = targ.getNextHighestDepth();
      var _loc1_ = targ.attachMovie(link,"oh" + _loc3_,_loc3_,{_x:_loc4_.x,_y:_loc4_.y});
      _loc1_.createTextField("res_txt",10,-10,-10,60,20);
      _loc1_.res_txt.textColor = 16777215;
      _loc1_.res_txt.text = cell.gx + ":" + cell.gy;
      return _loc1_;
   }
   function attachNPC(linkID, pos)
   {
      var _loc2_ = this.currentLocation.getCellFromNumber(pos);
      var _loc6_ = _loc2_.rx;
      var _loc5_ = _loc2_.ry;
      var _loc4_ = _loc2_.getMinDepth();
      var _loc3_ = this.core_mc.attachMovie(linkID,linkID,_loc4_);
      _loc3_._x = _loc6_;
      _loc3_._y = _loc5_;
   }
   function moveWalker(obj)
   {
      this.buildPath(obj.id,obj.path);
   }
   function buildPath(id, path)
   {
      if(!this.path_arr)
      {
         this.path_arr = new Array();
      }
      this.clearPath(id);
      var _loc3_ = 0;
      var _loc7_;
      var _loc6_;
      while(_loc3_ < path.length)
      {
         _loc7_ = path[_loc3_];
         _loc6_ = this.buildHex("obstPathHex",_loc7_,this.target.obst_mc);
         this.path_arr[id].push(_loc6_);
         _loc3_ = _loc3_ + 1;
      }
      var _loc4_ = this.currentLocation.locationGrid.CellsGrid;
      _loc3_ = 0;
      var _loc2_;
      var _loc5_;
      while(_loc3_ < _loc4_.length)
      {
         _loc2_ = 0;
         while(_loc2_ < _loc4_[_loc3_].length)
         {
            if(_loc4_[_loc3_][_loc2_].busy)
            {
               _loc5_ = this.buildHex("obstHex",_loc4_[_loc3_][_loc2_],this.target.obst_mc);
               this.busy_arr.push(_loc5_);
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc3_ = _loc3_ + 1;
      }
   }
   function clearPath(id)
   {
      for(var _loc3_ in this.path_arr[id])
      {
         this.path_arr[id][_loc3_].removeMovieClip();
      }
      for(_loc3_ in this.busy_arr)
      {
         this.busy_arr[_loc3_].removeMovieClip();
      }
      this.path_arr[id] = new Array();
      this.busy_arr = new Array();
   }
   function drawSOFronts(obj)
   {
      for(var _loc7_ in this.target.obst_mc)
      {
         this.target.obst_mc[_loc7_].removeMovieClip();
      }
      var _loc2_ = 0;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      while(_loc2_ < obj.front.length)
      {
         _loc6_ = obj.front[_loc2_].x;
         _loc5_ = obj.front[_loc2_].y;
         _loc4_ = this.target.getCellFromGrid(_loc6_,_loc5_);
         this.buildHex("obstPathHex",_loc4_,this.target.obst_mc);
         _loc2_ = _loc2_ + 1;
      }
   }
   function get currentLocation()
   {
      var _loc1_ = lol.core.Master.getInstance();
      return _loc1_.currentLocation;
   }
   function kill()
   {
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("LOCBUILDER" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
