class lol.gpui.controls.ChannelButton extends lol.gpui.GPUIObject
{
   var _data;
   var _parent;
   var backButton;
   var close_btn;
   var dispatchEvent;
   var light_mc;
   var startChat_btn;
   var title_mc;
   var light = false;
   function ChannelButton()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.backButton.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this._onPress);
      this.backButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this._onRelease);
      this.backButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this._onReleaseOutside);
      this.backButton.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this._onRollOver);
      this.startChat_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this);
      this.startChat_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this);
      this.startChat_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this);
      this.startChat_btn.addEventListener("startChat",this);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.closeChannel);
      this.doLater("showLight",[this.light]);
   }
   function closeChannel()
   {
      this.dispatchEvent({type:"closeChannel"});
   }
   function _onPress()
   {
      this.dispatchEvent({type:"onPress"});
   }
   function _onRelease()
   {
      this.dispatchEvent({type:"onRelease"});
   }
   function _onReleaseOutside()
   {
      this.dispatchEvent({type:"onReleaseOutside"});
   }
   function _onRollOver()
   {
      this.dispatchEvent({type:"onRollOver"});
   }
   function showLight(flag)
   {
      this.light = flag;
      this.light_mc._alpha = 0;
      if(flag && !this.backButton.toggled)
      {
         delete this.light_mc.onEnterFrame;
         var counter = 0;
         var step = 25;
         this.light_mc.onEnterFrame = function()
         {
            this._parent.light_mc._alpha += step;
            if(this._parent.light_mc._alpha >= 100 || this._parent.light_mc._alpha <= 0)
            {
               step = - step;
               counter++;
               if(counter == 5)
               {
                  delete this._parent.light_mc.onEnterFrame;
               }
            }
         };
      }
      else
      {
         this.light = false;
      }
   }
   function set name(value)
   {
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      this.title_mc.title.text = value;
      this.title_mc.title.setTextFormat(_loc2_);
   }
   function set label(l)
   {
      this.doLater("setLabel",[l]);
   }
   function setLabel(l)
   {
      this.backButton.label = l;
   }
   function get label()
   {
      return this.backButton.label;
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
      this.backButton.setStyle(obj);
   }
}
