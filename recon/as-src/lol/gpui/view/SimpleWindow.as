class lol.gpui.view.SimpleWindow extends lol.gpui.GPUIObject
{
   var _content;
   var _parent;
   var _x;
   var _xmouse;
   var _y;
   var _ymouse;
   var back_mc;
   var closeBtn;
   var closeBtn_mc;
   var close_btn;
   var cont_mc;
   var createEmptyMovieClip;
   var dispatchEvent;
   var maxX;
   var maxY;
   var minX;
   var minY;
   var mode;
   var modeLink;
   var onMouseMove;
   var stopDrag;
   var takeX;
   var takeY;
   var winID;
   var d = 0;
   var isDrag = false;
   var padding = 20;
   function SimpleWindow()
   {
      super();
      this.init();
   }
   function init()
   {
      if(!this.cont_mc)
      {
         this.cont_mc = this.createEmptyMovieClip("cont_mc",1);
         this.cont_mc._x = this.d;
         this.cont_mc._y = this.d;
      }
      if(this.close_btn)
      {
      }
      this.close_btn.onPress = mx.utils.Delegate.create(this,this.close);
      lol.core.SceneShifter._ref.addEventListener("resizeStage",this);
      this.doLater("init_drag");
   }
   function kill()
   {
      this.content.kill();
      this.closeBtn_mc.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter._ref.removeEventListener("resizeStage",this);
   }
   function resizeStage(obj)
   {
      this.modeLink._width = Stage.width;
      this.modeLink._height = obj.h;
      this.modeLink._x = (- Stage.width) / 2;
      this.modeLink._y = (- Stage.height) / 2;
   }
   function init_drag()
   {
      if(this._content.bg)
      {
         this._content.bg.onPress = mx.utils.Delegate.create(this,this.drag);
         this._content.bg.onRelease = mx.utils.Delegate.create(this,this.finishDrag);
         this._content.bg.onReleaseOutside = mx.utils.Delegate.create(this,this.finishDrag);
      }
      else
      {
         if(!this.back_mc)
         {
            this.back_mc = this.createEmptyMovieClip("back_mc",0);
         }
         this.back_mc.onPress = mx.utils.Delegate.create(this,this.drag);
         this.back_mc.onRelease = mx.utils.Delegate.create(this,this.finishDrag);
         this.back_mc.onReleaseOutside = mx.utils.Delegate.create(this,this.finishDrag);
      }
      this._content.bg.useHandCursor = false;
      this.back_mc.useHandCursor = false;
      this.noDragMode();
   }
   function drag()
   {
      lol.core.SceneShifter.sortWindows(this.winID,this);
      if(this.isDrag)
      {
         this.takeX = this._xmouse;
         this.takeY = this._ymouse;
         this.onMouseMove = this.moveWindow;
      }
   }
   function finishDrag()
   {
      this.stopDrag();
      delete this.onMouseMove;
   }
   function moveWindow()
   {
      this._x = Math.round(this._parent._xmouse - this.takeX);
      this._y = Math.round(this._parent._ymouse - this.takeY);
      this.checkPosition();
   }
   function checkPosition()
   {
      var _loc3_ = this._x;
      var _loc2_ = this._y;
      this.minX = (- Stage.width) / 2 + this.padding;
      this.minY = (- Stage.height) / 2 + this.padding;
      if(this._content.bg)
      {
         this.maxX = Stage.width / 2 - this._content.bg._width - this.padding;
         this.maxY = Stage.height / 2 - this._content.bg._height - this.padding - (Stage.height - lol.core.SceneShifter._ref.H) - 144;
      }
      else
      {
         this.maxX = Stage.width / 2 - this._content._width - this.padding;
         this.maxY = Stage.height / 2 - this._content._height - this.padding - (Stage.height - lol.core.SceneShifter._ref.H) - 144;
      }
      if(_loc3_ > this.maxX)
      {
         _loc3_ = this.maxX;
      }
      if(_loc3_ < this.minX)
      {
         _loc3_ = this.minX;
      }
      if(_loc2_ > this.maxY)
      {
         _loc2_ = this.maxY;
      }
      if(_loc2_ < this.minY)
      {
         _loc2_ = this.minY;
      }
      this._x = Math.round(_loc3_);
      this._y = Math.round(_loc2_);
   }
   function close()
   {
      this.dispatchEvent({type:"close"});
      lol.core.SceneShifter.closeWindow(this.winID);
   }
   function closeWindow()
   {
      this.dispatchEvent({type:"close"});
      lol.core.SceneShifter.closeWindow(this.winID);
   }
   function addCloseBtn()
   {
      this.removeCloseBtn();
      this.closeBtn_mc = this.cont_mc.attachMovie("closeWindow_mc","close_btn",100);
      this.closeBtn_mc._x = this._content._x + this._content.bg._x + this._content.bg._width - this.closeBtn_mc._width;
      this.closeBtn_mc._y = this._content._y + this._content.bg._y;
      this.doLater("initListener");
   }
   function removeCloseBtn()
   {
      this.closeBtn_mc.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.closeWin);
      this.closeBtn_mc.removeMovieClip();
   }
   function initListener(mc)
   {
      this.closeBtn_mc.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.closeWin);
   }
   function closeWin()
   {
      this._content.close();
   }
   function fillContent(linkID)
   {
      this._content = this.cont_mc.attachMovie(linkID,"_content",0);
      this._content.mode = this.mode;
      this._content.modeLink = this.modeLink;
      if(this._content instanceof lol.gpui.view.SimpleWindow)
      {
         this._content.addEventListener("resize",this);
      }
      this.resize();
      if(this.closeBtn)
      {
         this.addCloseBtn();
      }
      this._content.addEventListener("closeWindow",this);
   }
   function set content(linkID)
   {
      this._content = this.cont_mc.attachMovie(linkID,"_content",0);
      if(this._content instanceof lol.gpui.view.SimpleWindow)
      {
         this._content.addEventListener("resize",this);
      }
      this.resize();
   }
   function get content()
   {
      this.doLater(this,"resize");
      return this._content;
   }
   function resize()
   {
      var _loc2_ = this._content._width + 2 * this.d;
      var _loc3_ = this._content._height + 2 * this.d;
      this.back_mc.clear();
      if(this.isDrag)
      {
         lol.utils.Draw.drawFillRect(this.back_mc,0,0,_loc2_,_loc3_,1,0,0,0,0);
      }
      this.close_btn._y = 2;
      this.close_btn._x = _loc2_ - this.close_btn._width - 2;
      this.dispatchEvent({type:"resize"});
   }
   function dragMode()
   {
   }
   function noDragMode()
   {
   }
}
