class lol.gpui.MiniMapPan extends lol.gpui.GPUIObject
{
   var BY;
   var TY;
   var _y;
   var attachMovie;
   var back_btn;
   var closeEQ;
   var content;
   var doLater;
   var hideMiniMapPan_btn;
   var locationMap;
   var onEnterFrame;
   var openEQ;
   var title_txt;
   var viewSquare;
   var panActivationFlag = false;
   var mmW = 96;
   var mmH = 96;
   function MiniMapPan()
   {
      super();
      this.panActivationFlag = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.MINI_MAP_OPEN);
      if(this.panActivationFlag)
      {
         this._y = 49;
         this.showMM(true);
      }
      else
      {
         this._y = -70;
      }
      this.propeties();
      this.back_btn.useHandCursor = false;
      this.doLater("init");
   }
   function init()
   {
      var _loc2_ = lol.core.Master.getInstance().currentLocation;
      var _loc3_ = "[" + _loc2_.locationGrid.gridW + "x" + _loc2_.locationGrid.gridH + "]";
      this.title_txt.text = _loc2_.locationName + " " + _loc3_;
      this.hideMiniMapPan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.MINI_MAP,this,this.panActivation);
      this.locationMap = lol.core.SceneShifter.locationScreen.locationFrame;
      this.doLater("showMM",[this.panActivationFlag]);
   }
   function kill()
   {
      this.hideMiniMapPan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.MINI_MAP,this,this.panActivation);
   }
   function propeties()
   {
      this.TY = 49;
      this.BY = this.TY - 120;
      this.openEQ = new lol.events.EventQueue();
      this.openEQ.addEvent(this,"showMM",[true],0);
      this.openEQ.addEvent(this,"slide",[this.TY],0);
      this.closeEQ = new lol.events.EventQueue();
      this.closeEQ.addEvent(this,"slide",[this.BY],0);
      this.closeEQ.addEvent(this,"showMM",[false],200);
   }
   function slide(y)
   {
      this.onEnterFrame = function()
      {
         this._y += (y - this._y) / 2;
         if(Math.abs(y - this._y) < 2)
         {
            this._y = y;
            delete this.onEnterFrame;
         }
      };
   }
   function showMM(flag)
   {
      if(flag)
      {
         this.content = this.attachMovie("locMM","locMM",100);
         this.content._x = 15;
         this.content._y = 27;
         this.locationMap.addEventListener("position",this);
         this.viewSquare = this.content.viewSquare;
         lol.core.SceneShifter._ref.addEventListener("resizeStage",this);
         lol.core.SceneShifter._ref.setMCSize();
      }
      else
      {
         this.content.removeMovieClip();
         this.locationMap.removeEventListener("position",this);
         this.viewSquare = null;
         lol.core.SceneShifter._ref.removeEventListener("resizeStage",this);
      }
   }
   function position(obj)
   {
      var _loc3_ = obj.xpos;
      var _loc2_ = obj.ypos;
      var _loc5_ = (this.mmW - this.viewSquare._width) * _loc3_ / 100;
      var _loc4_ = (this.mmH - this.viewSquare._height) * _loc2_ / 100;
      this.viewSquare._x = _loc5_;
      this.viewSquare._y = _loc4_;
   }
   function resizeStage()
   {
      this.doLater("setSize");
   }
   function setSize()
   {
      var _loc3_ = this.locationMap.maskW * 100 / this.locationMap.content._width;
      var _loc2_ = this.locationMap.maskH * 100 / this.locationMap.content._height;
      this.viewSquare._width = this.mmW * _loc3_ / 100;
      this.viewSquare._height = this.mmH * _loc2_ / 100;
      this.locationMap.dispatchPosition();
   }
   function panActivation()
   {
      this.panActivationFlag = !this.panActivationFlag;
      if(this.panActivationFlag)
      {
         this.openEQ.Start();
      }
      else
      {
         this.closeEQ.Start();
      }
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.MINI_MAP_OPEN,this.panActivationFlag);
   }
}
