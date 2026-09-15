class lol.gpui.controls.GPUIButton extends lol.gpui.GPUIObject
{
   var _alpha;
   var _data;
   var _height;
   var _label;
   var _width;
   var _xmouse;
   var _ymouse;
   var attachMovie;
   var back_mc;
   var createEmptyMovieClip;
   var dispatchEvent;
   var enabled_mc;
   var getNextHighestDepth;
   var gotoAndStop;
   var hintTitle_str;
   var label_txt;
   var onMouseDown;
   var style;
   static var backSkinBD;
   var clickEvent = "click";
   var _enabled = true;
   static var PRESS_EVENT = "click";
   static var RELEASE_EVENT = "release";
   static var RELEASE_OUTSIDE_EVENT = "releaseOutside";
   static var ROLL_OVER_EVENT = "rollOver";
   static var ROLL_OUT_EVENT = "rollOut";
   static var DOUBLE_CLICK = "onDoubleClick";
   static var SHOW_HINT = "showHint";
   static var REMOVE_HINT = "removeHint";
   var enabledParam = true;
   static var defaultStyle = {color0:0,color1:16711680};
   static var lavaStyle0 = {color0:13421772,color1:16777215};
   static var lavaStyle1 = {color0:0,color1:16777215};
   function GPUIButton()
   {
      super();
      this.style = new Object();
      this.gotoAndStop(1);
      if(this.label_txt.text.length > 0)
      {
         this.label = this.label_txt.text;
      }
      this.enabled_mc = this.createEmptyMovieClip("enabled_mc",this.getNextHighestDepth());
      lol.utils.Draw.drawFillRect(this.enabled_mc,0,0,this._width,this._height,1,0,0,0,40);
      this.enabled_mc._visible = false;
      this.doLater("init");
   }
   function init()
   {
      lol.utils.EMouse.addEventListener(lol.utils.EMouse.DOUBLE_CLICK,this,this.doubleClick);
   }
   function doubleClick()
   {
      if(this._xmouse > 0 && this._xmouse < this._width && this._ymouse > 0 && this._ymouse < this._height)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.DOUBLE_CLICK});
      }
   }
   function onPress()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.PRESS_EVENT});
      }
      this.gotoAndStop(2);
      this.showHint(false);
      lol.gpui.HintManager.closeHint();
   }
   function onRelease()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.RELEASE_EVENT});
      }
      this.gotoAndStop(1);
      this.showHint(false);
   }
   function onRollOver()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT});
      }
      if(this.hintTitle_str)
      {
         lol.gpui.HintManager.showHint(this.hintTitle_str,this._ymouse,this._width - this._ymouse);
      }
      this.showHint(true);
   }
   function onRollOut()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT});
      }
      lol.gpui.HintManager.closeHint();
      this.showHint(false);
   }
   function onReleaseOutside()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT});
      }
      this.gotoAndStop(1);
      this.showHint(false);
      lol.gpui.HintManager.closeHint();
   }
   function showHint(b)
   {
      if(b == undefined)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.SHOW_HINT});
         this.onMouseDown = this.removeHint;
         return undefined;
      }
      if(!b)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.REMOVE_HINT});
      }
      else
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.SHOW_HINT});
      }
   }
   function removeHint()
   {
      delete this.onMouseDown;
      this.showHint(false);
   }
   function set label(l)
   {
      if(!this._label)
      {
         this.createLabel(l);
      }
      else
      {
         this.presetLabel(l);
      }
   }
   function get label()
   {
      if(typeof this._label == "movieclip")
      {
         return this._label.label;
      }
      return this._label.text;
   }
   function presetLabel(l)
   {
      if(typeof this._label == "movieclip")
      {
         this._label.label = l;
      }
      else
      {
         this._label.autoSize = true;
         this._label.text = l;
      }
      this.doLater("checkPosition");
   }
   function createLabel(l)
   {
      this._label = this.attachMovie("gpuiLabel","_label",2);
      this._label.label = l;
      this.doLater("checkPosition");
   }
   function checkPosition()
   {
   }
   function set enabled(e)
   {
      this._enabled = e;
      if(e)
      {
         this._alpha = 100;
         this.enabled_mc._visible = false;
      }
      else
      {
         this._alpha = 100;
         this.enabled_mc._visible = true;
      }
      this.showHint(false);
   }
   function get enabled()
   {
      return this._enabled;
   }
   function drawBorder()
   {
      if(!this.back_mc)
      {
         this.back_mc = this.createEmptyMovieClip("back_mc",0);
         this.back_mc.clear();
         lol.utils.Draw.drawFillRect(this,0,0,this._width,this._height,1,0,100,16777215,100);
      }
   }
   function set data(d)
   {
      this._data = d;
   }
   function get data()
   {
      return this._data;
   }
   function setStyle(obj)
   {
      this.style = obj;
      this._label.textColor = this.style.color0;
   }
   static function setSkin(bm)
   {
      lol.gpui.controls.GPUIButton.backSkinBD = bm;
   }
   function drawSkinBG()
   {
      if(!lol.gpui.controls.GPUIButton.backSkinBD)
      {
      }
   }
}
