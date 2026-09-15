class lol.gpui.EffectsPan extends lol.gpui.GPUIObject
{
   var BX;
   var TX;
   var _x;
   var _y;
   var attachMovie;
   var back_btn;
   var closeEQ;
   var content;
   var doLater;
   var hideFXPan_btn;
   var onEnterFrame;
   var openEQ;
   var panActivationFlag = false;
   function EffectsPan()
   {
      super();
      this.panActivationFlag = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.FX_PAN_OPEN);
      this._y = 10;
      if(this.panActivationFlag)
      {
         this._x = 45;
         this.showFX(true);
      }
      else
      {
         this._x = -40;
      }
      this.properties();
      this.back_btn.useHandCursor = false;
      this.doLater("init");
   }
   function init()
   {
      this.hideFXPan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      this.doLater("showFX",[this.panActivationFlag]);
   }
   function kill()
   {
      this.content.kill();
      this.hideFXPan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FX_PAN,this,this.panActivation);
   }
   function properties()
   {
      this.TX = 45;
      this.BX = this.TX - 70;
      this.openEQ = new lol.events.EventQueue();
      this.openEQ.addEvent(this,"showFX",[true],0);
      this.openEQ.addEvent(this,"slide",[this.TX],0);
      this.closeEQ = new lol.events.EventQueue();
      this.closeEQ.addEvent(this,"slide",[this.BX],0);
      this.closeEQ.addEvent(this,"showFX",[false],200);
   }
   function slide(x)
   {
      this.onEnterFrame = function()
      {
         this._x += (x - this._x) / 2;
         if(Math.abs(x - this._x) < 2)
         {
            this._x = x;
            delete this.onEnterFrame;
         }
      };
   }
   function showFX(show_flag)
   {
      if(show_flag)
      {
         this.content = this.attachMovie("fxCanvas","fxCanvas",100);
         this.content._x = 0;
         this.content._y = 15;
      }
      else
      {
         this.content.removeMovieClip();
      }
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
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.FX_PAN_OPEN,this.panActivationFlag);
   }
}
