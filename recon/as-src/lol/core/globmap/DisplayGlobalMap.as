class lol.core.globmap.DisplayGlobalMap extends MovieClip
{
   var activateContextMenu;
   var allNamesShowing;
   var clickPoint;
   var curScaleType;
   var delegatePlayerPosition;
   var dispatchEvent;
   var landscape;
   var markManager;
   var marks_mc;
   var master;
   var objects_mc;
   var onEnterFrame;
   var playerList;
   var userData;
   function DisplayGlobalMap()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      this.playerList = new Array();
      this.marks_mc = this.createEmptyMovieClip("marks_mc",7);
      this.objects_mc = this.createEmptyMovieClip("objects_mc",6);
      this.master = lol.core.Master.getInstance();
      this.userData = new Object();
      this.createLandscape();
      this.onEnterFrame = this.init;
      this.allNamesShowing = false;
      this.activateContextMenu = false;
      this.clickPoint = new flash.geom.Point(0,0);
   }
   function init()
   {
      delete this.onEnterFrame;
      var _loc4_ = this.globalMap.playerList;
      var _loc3_;
      var _loc2_;
      for(var _loc5_ in _loc4_)
      {
         _loc3_ = _loc4_[_loc5_];
         _loc2_ = this.addPlayer({player:_loc3_});
         if(_loc3_ == this.master.gamer)
         {
            this.configurePlayerMO(_loc2_);
         }
      }
      this.globalMap.addEventListener("addPlayer",this);
      this.globalMap.addEventListener("faraway",this);
      this.globalMap.addEventListener("near",this);
      this.globalMap.addEventListener("lost",this);
      this.globalMap.addEventListener("position",this);
      this.centerChar(false);
   }
   function configurePlayerMO(displayPlayer)
   {
      var _loc2_ = this.globalMap.gamer;
      var _loc3_ = _loc2_.walker.v_rad * this.mapScale;
      if(displayPlayer.persID == lol.core.Master.getInstance().gamer.id)
      {
         displayPlayer.showVisRad(_loc3_);
         displayPlayer.c_mc.gotoAndStop(2);
      }
      _loc2_.walker.addEventListener("position",this,this.observePlayer);
   }
   function addPlayer(obj)
   {
      var _loc3_ = obj.player.id;
      var _loc7_ = this.objects_mc.getNextHighestDepth();
      var _loc2_ = this.objects_mc.attachMovie("mU","mo" + _loc3_,_loc7_,{id:_loc3_});
      _loc2_.persID = _loc3_;
      this.playerList[_loc3_] = _loc2_;
      var _loc5_ = obj.player.walker.x;
      var _loc4_ = obj.player.walker.y;
      var _loc8_ = new lol.utils.Timeout(this,this.initListeners,500,_loc2_);
      this.moveObject(_loc2_,_loc5_,_loc4_);
      _loc2_.coordinate_str = _loc5_ + " " + _loc4_;
      if(_loc3_ != lol.core.player.Gamer.ID)
      {
         _loc2_.vrad_mc._visible = false;
         _loc2_.vrad_mc.gotoAndStop(3);
      }
      return _loc2_;
   }
   function initListeners(mc)
   {
      mc.addEventListener("playerOnPress",this,this.playerMcOnPress);
      mc.addEventListener("playerOnRelease",this,this.playerMcOnRelease);
   }
   function playerMcOnPress(obj)
   {
      var _loc2_;
      if(obj.target.persID && this.activateContextMenu)
      {
         this.clickPoint.x = this._xmouse;
         this.clickPoint.y = this._ymouse;
         this.dispatchEvent({type:"releaseMap"});
         _loc2_ = new Array();
         _loc2_.push({linkID:"actionIntercept_btn",obj:this,function_str:"actionIntercept",data:obj.target.persID});
         _loc2_.push({linkID:"actionPrivat_btn",obj:this,function_str:"actionPrivat",data:obj.target.persID});
         _loc2_.push({linkID:"actionCome_btn",obj:this,function_str:"actionMove",data:obj.target.persID});
         lol.core.SceneShifter.contextMenuManager.openContextMenu(_loc2_,"actionDropList",obj.target.persName_str);
         lol.core.SceneShifter.contextMenuManager.addEventListener("selectItem",this,this.clickContext);
      }
      else
      {
         this.dispatchEvent({type:"unlockMapAndMove"});
      }
   }
   function clickContext(obj)
   {
      obj.target.removeEventListener("selectItem",this,this.clickContext);
      if(obj.data.function_str == "actionMove")
      {
         this.playerMoveToPoint(this.clickPoint);
      }
      else if(obj.data.function_str == "actionIntercept")
      {
         this.globalMap.interceptPlayer(obj.data.param,true);
      }
      else if(obj.data.function_str == "actionPrivat")
      {
         lol.core.SceneShifter.chat.setPrivateToInputStr(obj.data.param);
      }
   }
   function playerMcOnRelease()
   {
   }
   function removePlayer(obj)
   {
      var _loc3_ = obj.player.id;
      var _loc2_ = this.playerList[_loc3_];
      _loc2_.removeEventListener("playerOnPress",this,this.playerMcOnPress);
      _loc2_.removeEventListener("playerOnRelease",this,this.playerMcOnRelease);
      delete this.playerList[_loc3_];
      this.playerList[_loc3_] = null;
      _loc2_.removeMovieClip();
   }
   function moveObject(obj, x, y)
   {
      obj._x = this.mapScale * x;
      obj._y = this.mapScale * y;
   }
   function playerMove()
   {
      var _loc2_ = this.globalMap.gamer;
      var _loc4_ = Math.floor(100 * (this._xmouse / this.mapScale - _loc2_.walker.x));
      var _loc3_ = Math.floor(100 * (this._ymouse / this.mapScale - _loc2_.walker.y));
      this.globalMap.playerMove(_loc4_,_loc3_);
   }
   function playerMoveToPoint(point)
   {
      this.playerMoveToCoords(point.x,point.y);
   }
   function playerMoveToCoords(X, Y)
   {
      var _loc2_ = this.globalMap.gamer;
      var _loc4_ = Math.floor(100 * (X / this.mapScale - _loc2_.walker.x));
      var _loc3_ = Math.floor(100 * (Y / this.mapScale - _loc2_.walker.y));
      this.globalMap.playerMove(_loc4_,_loc3_);
   }
   function position(obj)
   {
      var _loc2_ = obj.walker.id;
      var _loc5_ = obj.walker.x;
      var _loc4_ = obj.walker.y;
      var _loc3_ = this.playerList[_loc2_];
      this.moveObject(_loc3_,_loc5_,_loc4_);
      _loc3_.coordinate_str = _loc5_ + " " + _loc4_;
      if(_loc2_ == lol.core.player.Gamer.ID)
      {
      }
   }
   function faraway(obj)
   {
      var _loc2_ = obj.id;
      var _loc3_ = this.playerList[_loc2_];
      _loc3_.fade();
   }
   function near(obj)
   {
      var _loc2_ = obj.id;
      var _loc3_ = this.playerList[_loc2_];
      _loc3_.normal();
   }
   function lost(obj)
   {
      var _loc2_ = obj.id;
      var _loc4_ = this.playerList[_loc2_];
      this.removePlayer(obj);
   }
   function createLandscape()
   {
      this.landscape = new lol.core.globmap.DisplayLandscape();
      this.landscape.land_mc = this.createEmptyMovieClip("land_mc",2);
      this.landscape.temp_grid_mc = this.createEmptyMovieClip("temp_grid_mc",3);
      this.landscape.grid_mc = this.createEmptyMovieClip("grid_mc",4);
   }
   function observePlayer(obj)
   {
      var _loc5_ = obj.target.id;
      var _loc6_ = this.playerList[_loc5_];
      var _loc2_ = obj.target;
      var _loc4_ = _loc2_.x;
      var _loc3_ = _loc2_.y;
      this.userData.px = this.userData.cx;
      this.userData.py = this.userData.cy;
      this.userData.cx = Math.floor(this.landscape.mapScale * _loc4_ / this.landscape.cellSize);
      this.userData.cy = Math.floor(this.landscape.mapScale * _loc3_ / this.landscape.cellSize);
      if(this.userData.cx != this.userData.px || this.userData.cy != this.userData.py)
      {
         this.landscape.addEventListener("build",this,this.centerCharAfterBuild);
         this.landscape.drawArea(_loc4_,_loc3_);
      }
   }
   function centerChar(how)
   {
      var _loc2_ = this.globalMap.gamer;
      var _loc4_ = new Object();
      _loc4_.x = this.mapScale * _loc2_.walker.x;
      _loc4_.y = this.mapScale * _loc2_.walker.y;
      this.dispatchEvent({type:"centerPoint",point:_loc4_,how:how});
   }
   function onMouseMove()
   {
      var _loc3_ = Math.ceil(this._xmouse / this.mapScale) - 1;
      var _loc2_ = Math.ceil(this._ymouse / this.mapScale) - 1;
      this.dispatchEvent({type:"cursorPosition",x:_loc3_,y:_loc2_,mapScale:this.mapScale});
   }
   function addMark(mark, type)
   {
      if(!this.markManager)
      {
         this.markManager = new lol.core.globmap.MarkManager(this.marks_mc);
      }
      var _loc2_ = this.markManager.addMark(mark,type);
      this.moveObject(_loc2_,mark.x,mark.y);
      return _loc2_;
   }
   function removeMark(mark)
   {
      this.markManager.removeMark(mark);
   }
   function updateMark(mark)
   {
      this.markManager.updateMark(mark);
   }
   function selectMark(mark)
   {
      this.markManager.selectMark(mark);
   }
   function getMouseCoord()
   {
      var _loc4_ = this.marks_mc._xmouse / this.mapScale;
      var _loc3_ = this.marks_mc._ymouse / this.mapScale;
      var _loc2_ = new flash.geom.Point(_loc4_,_loc3_);
      return _loc2_;
   }
   function scaleUp()
   {
      this.setScale(lol.core.globmap.DisplayLandscape.FULL);
   }
   function scaleDown()
   {
      this.setScale(lol.core.globmap.DisplayLandscape.SMALL);
   }
   function setScale(type)
   {
      this.landscape.setScale(type);
      this.redrawMap();
   }
   function redrawMap()
   {
      var _loc4_;
      var _loc3_;
      var _loc12_;
      var _loc11_;
      var _loc10_;
      for(var _loc8_ in this.globalMap.playerList)
      {
         _loc4_ = this.globalMap.playerList[_loc8_].id;
         _loc3_ = this.globalMap.playerList[_loc8_];
         _loc12_ = _loc3_.walker.x;
         _loc11_ = _loc3_.walker.y;
         _loc10_ = this.playerList[_loc4_];
         this.moveObject(_loc10_,_loc12_,_loc11_);
      }
      var _loc2_;
      var _loc5_;
      var _loc6_;
      for(_loc8_ in this.markManager.markList)
      {
         _loc2_ = this.markManager.markList[_loc8_].markObj;
         _loc5_ = this.markManager.getMarkNum(_loc2_);
         _loc6_ = this.markManager.markList[_loc5_];
         this.moveObject(_loc6_,_loc2_.x,_loc2_.y);
      }
      var _loc7_ = this.globalMap.gamer;
      _loc12_ = _loc7_.walker.x;
      _loc11_ = _loc7_.walker.y;
      var _loc9_ = _loc7_.walker.v_rad * this.mapScale;
      _loc10_ = this.playerList[_loc7_.id];
      if(_loc7_.id == lol.core.Master.getInstance().gamer.id)
      {
         _loc10_.showVisRad(_loc9_);
      }
      this.landscape.addEventListener("build",this,this.centerCharAfterBuild);
      this.landscape.drawArea(_loc12_,_loc11_);
   }
   function centerCharAfterBuild(obj)
   {
      obj.target.removeEventListener("build",this,this.centerCharAfterBuild);
      if(this.landscape.mapScaleType != this.curScaleType)
      {
         this.curScaleType = this.landscape.mapScaleType;
         this.centerChar(false);
      }
   }
   function get mapScale()
   {
      return this.landscape.mapScale;
   }
   function kill()
   {
      this.globalMap.removeEventListener("addObject",this);
      this.globalMap.removeEventListener("faraway",this);
      this.globalMap.removeEventListener("near",this);
      this.globalMap.removeEventListener("lost",this);
      this.globalMap.removeEventListener("position",this);
      delete this.onMouseMove;
      var _loc2_ = this.globalMap.gamer;
      _loc2_.walker.removeEventListener("position",this,this.observePlayer);
      delete this.delegatePlayerPosition;
      delete this.globalMap;
      this.landscape.kill();
      delete this.landscape;
      this.removeMovieClip();
   }
   function get globalMap()
   {
      return this.master.globalMap;
   }
   function prepareForContextMenu(activate)
   {
      this.activateContextMenu = activate;
   }
   function showAllNames()
   {
      if(!this.allNamesShowing)
      {
         for(var _loc2_ in this.playerList)
         {
            this.playerList[_loc2_].ShowName();
         }
         this.allNamesShowing = true;
      }
   }
   function hideAllNames()
   {
      if(this.allNamesShowing)
      {
         for(var _loc2_ in this.playerList)
         {
            this.playerList[_loc2_].HideName();
         }
         this.allNamesShowing = false;
      }
   }
}
