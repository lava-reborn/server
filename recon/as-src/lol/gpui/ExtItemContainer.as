class lol.gpui.ExtItemContainer extends lol.gpui.ItemContainer
{
   var __item;
   var _width;
   var _xmouse;
   var _ymouse;
   var attachMovie;
   var bg_mc;
   var doLater;
   var getNextHighestDepth;
   var info_btn;
   var onMouseMove;
   var btnLinkID = "info_btn";
   function ExtItemContainer()
   {
      super();
      this.doLater("attachBtn");
   }
   function attachBtn()
   {
      var _loc2_ = this.__item.getProp("premium");
      var _loc3_;
      if(_loc2_ == 1 || _loc2_ == 2)
      {
         this.btnLinkID += "_premium";
      }
      else
      {
         _loc3_ = this.__item.getProp("g_cost");
         if(_loc3_)
         {
            this.btnLinkID += "_gold";
         }
      }
      var _loc4_ = this.getNextHighestDepth();
      this.info_btn = this.attachMovie(this.btnLinkID,this.btnLinkID,_loc4_);
      this.info_btn._x = this.bg_mc._width;
      this.info_btn.onRollOver = mx.utils.Delegate.create(this,this.rollOverBtn);
      this.info_btn.onRollOut = mx.utils.Delegate.create(this,this.rollOutBtn);
      this.info_btn.onRelease = mx.utils.Delegate.create(this,this.onPressBtn);
      this.info_btn.onReleaseOutside = mx.utils.Delegate.create(this,this.rollOutBtn);
   }
   function onPressBg()
   {
      this.dispatch({type:"_onMouseOut"});
      delete this.onMouseMove;
      super.onPressBg();
   }
   function onPressBtn()
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("annotation",undefined,undefined,this.__item.id);
      _loc2_.content.showInfo(this.__item,true);
      lol.gpui.AnnotationManager.clear();
   }
   function rollOverBtn()
   {
      this.toggled_frame = true;
      lol.gpui.AnnotationManager.create(this.__item,this._xmouse,this._width - this._xmouse,this._ymouse);
   }
   function rollOutBtn()
   {
      this.toggled_frame = this.toggled;
      this.dispatch({type:"_onRollOutAnnotation"});
      lol.gpui.AnnotationManager.clear();
   }
}
