class lol.gpui.dialogue.GPUIDialogueDelete extends lol.gpui.dialogue.GPUIDialogue
{
   var alert_txt;
   var apply_btn;
   var back_mc;
   var cancel_btn;
   var delete_mc;
   var delete_txt;
   var doLater;
   var checkBox_bool = false;
   function GPUIDialogueDelete()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      super.init();
      this.delete_txt = this.delete_mc.delete_txt;
      this.delete_txt.onChanged = mx.utils.Delegate.create(this,this.changeDeleteTxt);
      this.apply_btn.enabled = false;
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this._apply);
   }
   function kill()
   {
      super.kill();
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this._apply);
   }
   function _apply()
   {
      if(this.apply_btn.enabled)
      {
         super._apply();
      }
   }
   function changeDeleteTxt()
   {
      if(this.delete_txt.text == "УДАЛИТЬ")
      {
         this.apply_btn.enabled = true;
      }
      else
      {
         this.apply_btn.enabled = false;
      }
   }
   function resize()
   {
      var _loc4_ = this.back_mc.middle_mc._height;
      var _loc5_ = Math.floor((this.alert_txt._height + this.delete_mc._height + 10) / _loc4_);
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
      this.delete_mc._y = this.alert_txt._y + this.alert_txt._height + 10;
   }
}
