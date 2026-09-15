class lol.gpui.dialogue.GPUIDialogue extends lol.gpui.GPUIObject
{
   var alert_txt;
   var apply_btn;
   var back_mc;
   var cancel_btn;
   var dispatchEvent;
   var modeLink;
   var clickEvent = "click";
   function GPUIDialogue()
   {
      super();
      this.doLater(this,"init");
   }
   function init()
   {
      this.apply_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this._apply);
      this.cancel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this._cancel);
      lol.core.SceneShifter.hotKeyManager.addFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this._cancel);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this._apply);
   }
   function kill()
   {
      this.apply_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this._apply);
      this.cancel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this._cancel);
      lol.core.SceneShifter.hotKeyManager.removeFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this._cancel);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this._apply);
   }
   function _apply()
   {
      this.modeLink.removeMovieClip();
      this.dispatchEvent({type:this.clickEvent,success:true});
   }
   function _cancel()
   {
      this.modeLink.removeMovieClip();
      this.dispatchEvent({type:this.clickEvent,success:false});
   }
   function set label(str)
   {
      this.alert_txt.autoSize = true;
      this.alert_txt.multiline = true;
      this.alert_txt.html = true;
      this.alert_txt.htmlText = "<B>" + str + "</B>";
      if(this.alert_txt.textHeight >= 10)
      {
         this.resize();
      }
   }
   function get label()
   {
      return this.alert_txt.text;
   }
   function resize()
   {
      var _loc4_ = this.back_mc.middle_mc._height;
      var _loc5_ = Math.floor((this.alert_txt._height + 20) / _loc4_);
      var _loc3_;
      var _loc2_ = 0;
      while(_loc2_ < _loc5_)
      {
         _loc3_ = this.back_mc.middle_mc.duplicateMovieClip("m" + _loc2_,_loc2_);
         _loc3_._y = this.back_mc.top_mc._y + this.back_mc.top_mc._height + (_loc2_ + 1) * _loc4_;
         _loc2_ = _loc2_ + 1;
      }
      this.back_mc.bottom_mc._y = _loc3_._y + _loc3_._height;
      this.apply_btn._y = this.back_mc._height - 60;
      this.cancel_btn._y = this.back_mc._height - 60;
   }
}
